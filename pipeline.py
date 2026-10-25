# pipeline.py
# runs the whole thing:  pdfs -> pages -> chunks -> llm (in parallel) -> verify -> table
#
# speed comes from two ideas:
#   1. fewer calls: a few pages per llm call instead of one call per page
#   2. parallel calls: several chunks (from several papers) are sent at the same time
# so 20 papers dont take 20x as long as 1 paper.

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import cache
from ingest import fingerprint, make_chunks, property_words, read_pages, split_chunk
from prompt import build_prompt
from providers import AllProvidersFailed, BadOutputError, ask, new_router
from schema import clean_llm_row
from text_tools import normalize
from verify import verify_row

DEFAULT_WORKERS = 4


def failure(chunk, reason):
    info = {}
    info["pages"] = ", ".join(str(p) for p in chunk["pages"])
    info["reason"] = reason[:300]
    return info


def extract_chunk(router, chunk, target_properties):
    # one llm job. returns (raw rows, failures)
    prompt = build_prompt(chunk["text"], target_properties)
    try:
        rows, provider_name = ask(router, prompt)
    except BadOutputError as error:
        # the answer was probably cut off because the chunk had too much in it.
        # split it in half and try each half on its own
        if len(chunk["blocks"]) > 1:
            left, right = split_chunk(chunk)
            left_rows, left_failures = extract_chunk(router, left, target_properties)
            right_rows, right_failures = extract_chunk(router, right, target_properties)
            return left_rows + right_rows, left_failures + right_failures
        return [], [failure(chunk, "unreadable answer: " + str(error))]
    except AllProvidersFailed as error:
        return [], [failure(chunk, "all providers failed: " + str(error))]

    cleaned = []
    for raw in rows:
        row = clean_llm_row(raw)
        row["provider"] = provider_name
        cleaned.append(row)
    return cleaned, []


def remove_duplicates(rows):
    # the llm sometimes lists the same value twice
    seen = []
    unique = []
    for row in rows:
        signature = (
            row["paper"],
            normalize(row["material"]),
            normalize(row["property"]),
            normalize(row["value"]),
            normalize(row["unit"]),
            normalize(row["evidence"]),
        )
        if signature in seen:
            continue
        seen.append(signature)
        unique.append(row)
    return unique


def run(papers, target_properties, providers, workers=DEFAULT_WORKERS,
        filter_pages=True, use_cache=True, on_progress=None):
    # papers: list of {"name": file name, "bytes": pdf bytes}
    # on_progress(done, total, message): called from THIS thread, safe for streamlit
    start_time = time.time()
    router = new_router(providers)
    words = property_words(target_properties)

    # ---- stage 1 + 2: read every paper, reuse cached answers, plan the llm jobs ----
    infos = []
    jobs = []
    for paper in papers:
        info = {}
        info["name"] = paper["name"]
        info["pages"] = read_pages(paper["bytes"])
        info["cache_key"] = cache.cache_key(fingerprint(paper["bytes"]), target_properties, filter_pages)
        info["raw_rows"] = []
        info["failures"] = []
        info["pages_sent"] = 0
        info["from_cache"] = False

        cached_rows = None
        if use_cache:
            cached_rows = cache.load(info["cache_key"])

        if cached_rows is not None:
            info["raw_rows"] = cached_rows
            info["from_cache"] = True
        else:
            chunks, pages_kept = make_chunks(info["pages"], words, filter_pages)
            info["pages_sent"] = pages_kept
            for chunk in chunks:
                jobs.append((len(infos), chunk))

        infos.append(info)

    # ---- stage 3: send the llm jobs in parallel ----
    total = len(jobs)
    done = 0
    if on_progress is not None:
        on_progress(0, total, "starting")

    if total > 0:
        if len(providers) == 0:
            for paper_index, chunk in jobs:
                infos[paper_index]["failures"].append(failure(chunk, "no llm provider configured"))
        else:
            with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
                future_to_job = {}
                for paper_index, chunk in jobs:
                    future = pool.submit(extract_chunk, router, chunk, target_properties)
                    future_to_job[future] = (paper_index, chunk)

                # as_completed hands us each job the moment it finishes
                for future in as_completed(future_to_job):
                    paper_index, chunk = future_to_job[future]
                    info = infos[paper_index]
                    try:
                        rows, failures = future.result()
                    except Exception as error:
                        rows = []
                        failures = [failure(chunk, "unexpected error: " + str(error))]
                    info["raw_rows"].extend(rows)
                    info["failures"].extend(failures)

                    done = done + 1
                    if on_progress is not None:
                        message = info["name"] + " · pages " + ", ".join(str(p) for p in chunk["pages"])
                        on_progress(done, total, message)

    # save answers for papers that fully succeeded (so next time is instant)
    for info in infos:
        if use_cache and not info["from_cache"] and len(info["failures"]) == 0:
            cache.save(info["cache_key"], info["raw_rows"])

    # ---- stage 4: verify every row against its own paper ----
    table = []
    for info in infos:
        for raw in info["raw_rows"]:
            table.append(verify_row(raw, info["pages"], info["name"], target_properties))
    table = remove_duplicates(table)

    # ---- stats for the ui (and for the "how fast is it" slide) ----
    failures = []
    for info in infos:
        for item in info["failures"]:
            item_with_paper = {}
            item_with_paper["paper"] = info["name"]
            item_with_paper["pages"] = item["pages"]
            item_with_paper["reason"] = item["reason"]
            failures.append(item_with_paper)

    stats = {}
    stats["papers"] = len(infos)
    stats["pages_total"] = sum(len(info["pages"]) for info in infos)
    stats["pages_sent"] = sum(info["pages_sent"] for info in infos)
    stats["papers_from_cache"] = sum(1 for info in infos if info["from_cache"])
    stats["llm_jobs"] = total
    stats["calls_by_provider"] = dict(router["calls"])
    stats["disabled_providers"] = dict(router["disabled"])
    stats["call_log"] = list(router["log"])
    stats["seconds"] = round(time.time() - start_time, 1)

    result = {}
    result["rows"] = table
    result["failures"] = failures
    result["stats"] = stats
    return result
