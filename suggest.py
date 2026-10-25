# suggest.py
# "what can I even extract from these papers?"
# skims each paper, asks an engine which measurable properties it reports numbers for,
# then keeps ONLY the names that really appear in the paper's text (plain code, no trust).
# the researcher picks from the list, so they use the paper's own words as properties.

import hashlib
import re
from concurrent.futures import ThreadPoolExecutor

from rapidfuzz import fuzz

import cache
from ingest import fingerprint, read_pages
from providers import AllProvidersFailed, BadOutputError, ask, new_router
from text_tools import normalize, squash

SUGGEST_VERSION = "s1"     # bump when the prompt below changes, so old cached lists are ignored
MAX_PAPERS = 8              # suggestions from the first 8 papers are plenty
MAX_SKIM_CHARS = 8000       # per paper
FIRST_PAGE_CHARS = 3500     # title + abstract usually live here
TABLE_LINES = 14            # lines kept after each "Table n" caption
MAX_SUGGESTIONS = 12
NAME_MATCH_SCORE = 92       # how close a suggested name must be to text in the paper


def skim(pages):
    # the parts of a paper that say WHAT was measured: the abstract and the tables
    parts = []
    if len(pages) > 0:
        parts.append(pages[0]["text"][:FIRST_PAGE_CHARS])
    for page_info in pages:
        lines = page_info["text"].splitlines()
        for index in range(len(lines)):
            # a table caption, including "Supplementary Table 1" and "Table S2"
            if re.search(r"\btable\s*S?[0-9IVX]+\b", lines[index], re.IGNORECASE):
                parts.append("\n".join(lines[index:index + TABLE_LINES]))
    text = "\n[...]\n".join(parts)
    return text[:MAX_SKIM_CHARS]


def build_suggest_prompt(skim_text):
    prompt = ""
    prompt = prompt + "You help a researcher decide what data to extract from a scientific paper.\n\n"
    prompt = prompt + "Below is the abstract and the tables of one paper (PDF text, tables may be one cell per line).\n"
    prompt = prompt + "List the measurable properties this paper reports NUMERIC values for.\n"
    prompt = prompt + "Rules:\n"
    prompt = prompt + "- Use the property name exactly as the paper writes it (e.g. 'ionic conductivity', 'μC*').\n"
    prompt = prompt + "- Only properties with actual numbers in the text. No methods, no materials, no conditions "
    prompt = prompt + "like temperature or thickness unless they are a reported result.\n"
    prompt = prompt + "- 'unit' as written in the paper, or \"\" if none.\n"
    prompt = prompt + "- At most 10 items, most important first.\n"
    prompt = prompt + 'Return ONLY JSON: {"rows": [{"property": "...", "unit": "..."}]}\n\n'
    prompt = prompt + "PAPER TEXT:\n" + skim_text
    return prompt


def name_in_paper(name, paper_text):
    # the check that keeps suggestions honest: the name must really be in the paper
    target = normalize(name).lower().strip()
    if len(target) < 2:
        return False
    if target in paper_text:
        return True
    if len(target) >= 5 and fuzz.partial_ratio(target, paper_text) >= NAME_MATCH_SCORE:
        return True
    return False


def suggestion_cache_key(paper_bytes):
    recipe = "suggest|" + fingerprint(paper_bytes) + "|" + SUGGEST_VERSION
    return hashlib.sha256(recipe.encode("utf-8")).hexdigest()[:24]


def suggest_for_paper(router, name, paper_bytes, use_cache=True):
    # returns (list of {"property", "unit"} that passed the check, failure text or "")
    key = suggestion_cache_key(paper_bytes)
    pages = read_pages(paper_bytes)
    paper_text = normalize(" ".join(page_info["text"] for page_info in pages)).lower()

    rows = cache.load(key) if use_cache else None
    if rows is None:
        try:
            rows, provider_name = ask(router, build_suggest_prompt(skim(pages)))
        except (BadOutputError, AllProvidersFailed) as error:
            return [], name + ": " + str(error)[:200]
        cache.save(key, rows)

    kept = []
    for row in rows:
        prop = str(row.get("property", "") or "").strip()
        unit = str(row.get("unit", "") or "").strip()
        if prop == "" or len(prop) > 60:
            continue
        if name_in_paper(prop, paper_text):
            kept.append({"property": prop, "unit": unit})
    return kept, ""


def suggest(papers, providers, use_cache=True):
    # papers: {name: pdf bytes}. returns {"items": [...], "failures": [...], "papers": [...]}
    # each item: {"name", "unit", "papers": [paper names that report it]}
    names = list(papers.keys())[:MAX_PAPERS]
    result = {"items": [], "failures": [], "papers": list(papers.keys())}
    if len(names) == 0 or len(providers) == 0:
        return result

    router = new_router(providers)
    with ThreadPoolExecutor(max_workers=min(4, len(names))) as pool:
        futures = []
        for name in names:
            futures.append((name, pool.submit(suggest_for_paper, router, name, papers[name], use_cache)))
        per_paper = []
        for name, future in futures:
            kept, failure = future.result()
            per_paper.append((name, kept))
            if failure:
                result["failures"].append(failure)

    # merge across papers: same name (ignoring case and spaces) = one suggestion
    merged = {}
    order = []
    for name, kept in per_paper:
        for row in kept:
            key = squash(row["property"]).lower()
            if key not in merged:
                merged[key] = {"name": row["property"], "unit": row["unit"], "papers": []}
                order.append(key)
            if merged[key]["unit"] == "" and row["unit"] != "":
                merged[key]["unit"] = row["unit"]
            if name not in merged[key]["papers"]:
                merged[key]["papers"].append(name)

    # properties found in more papers first; ties keep the engine's "most important first" order
    order.sort(key=lambda key: -len(merged[key]["papers"]))
    for key in order[:MAX_SUGGESTIONS]:
        result["items"].append(merged[key])
    return result


def split_properties(text):
    parts = []
    for part in str(text or "").split(","):
        part = part.strip()
        if part != "":
            parts.append(part)
    return parts


def apply_selection(properties_text, all_suggestions, selected):
    # the properties box after the researcher toggles suggestion chips:
    # what they typed themselves stays, chips they turned off go, new chips are added at the end
    suggestion_keys = set(squash(name).lower() for name in all_suggestions)
    selected_keys = set(squash(name).lower() for name in selected)
    kept = []
    seen = set()
    for part in split_properties(properties_text):
        key = squash(part).lower()
        if key in suggestion_keys and key not in selected_keys:
            continue
        if key not in seen:
            kept.append(part)
            seen.add(key)
    for name in selected:
        key = squash(name).lower()
        if key not in seen:
            kept.append(name)
            seen.add(key)
    return ", ".join(kept)


def selected_in(properties_text, all_suggestions):
    # which chips should look "on", given what's in the properties box right now
    typed = set(squash(part).lower() for part in split_properties(properties_text))
    on = []
    for name in all_suggestions:
        if squash(name).lower() in typed:
            on.append(name)
    return on
