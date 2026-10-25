# app.py
# the screen. this file ONLY does user interface - all the real work
# lives in pipeline.py and the modules it calls. that way a ui change
# can never break extraction, and an extraction fix never breaks the ui.
#
# layout: a thread list on the left (like an llm app), one thread's workspace on the right.
# a thread = its own pdfs + properties + latest results, saved to .datum_threads/
# so threads survive a page reload.
#
# run with:  python -m streamlit run app.py

import os
import zlib

import pandas as pd
import streamlit as st

import pipeline
import suggest
import threads
import ui
from evaluate import evaluate, read_answer_key
from highlight import render_evidence
from providers import HEDGE_SECONDS, build_providers
from schema import STATUS_FLAGGED, STATUS_REVIEW, STATUS_VERIFIED

st.set_page_config(page_title="Datum", page_icon="◆", layout="wide", initial_sidebar_state="expanded")
st.markdown(ui.CSS, unsafe_allow_html=True)

STATUS_LABELS = {
    STATUS_VERIFIED: "✅ verified",
    STATUS_REVIEW: "🟡 review",
    STATUS_FLAGGED: "🚩 flagged",
}

# columns shown in the on-screen table (the csv download has all of them)
SCREEN_COLUMNS = [
    "status", "material", "property_std", "property", "value", "error", "unit",
    "value_std", "unit_std", "origin", "reference", "paper", "page", "checks",
]

FILTERS = {
    "All": [STATUS_VERIFIED, STATUS_REVIEW, STATUS_FLAGGED],
    "Verified": [STATUS_VERIFIED],
    "Review": [STATUS_REVIEW],
    "Flagged": [STATUS_FLAGGED],
}


# ---------------------------------------------------------
# api keys: environment variable first (local + streamlit cloud),
# then .streamlit/secrets.toml if one exists
# ---------------------------------------------------------
def get_secret(name):
    value = os.environ.get(name, "")
    if value:
        return value

    # only touch st.secrets when a secrets file exists, otherwise streamlit shows a warning
    secret_files = [
        os.path.join(os.getcwd(), ".streamlit", "secrets.toml"),
        os.path.join(os.path.expanduser("~"), ".streamlit", "secrets.toml"),
    ]
    for path in secret_files:
        if os.path.exists(path):
            try:
                return str(st.secrets.get(name, ""))
            except Exception:
                return ""
    if not is_local():
        # on streamlit cloud the secrets live outside the repo folder
        try:
            return str(st.secrets.get(name, ""))
        except Exception:
            return ""
    return ""


LANDING_URL = "https://neerajarde.github.io/datum/"


def is_local():
    # True when the app runs on this laptop (localhost), False on a public deploy
    try:
        host = st.context.headers.get("Host", "") or ""
    except Exception:
        host = ""
    host = host.split(":")[0].strip().lower()
    return host in ("localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]")


def pick_space():
    # local: one shared folder (it's your laptop). public: each browser gets its own space,
    # kept in the url (?w=...) so a reload still finds the threads.
    mode = os.environ.get("DATUM_SPACES", "").lower()
    if mode == "shared" or (mode != "private" and is_local()):
        return ""
    space = threads.clean_space(st.query_params.get("w", ""))
    if space == "":
        space = threads.clean_space(st.session_state.get("space", "")) or threads.new_space_id()
        st.query_params["w"] = space
    st.session_state["space"] = space
    return space


# ---------------------------------------------------------
# results: details, evidence, accuracy
# ---------------------------------------------------------
def show_engine_report(stats):
    # where did the time go? one line per engine
    log = stats.get("call_log", [])
    if len(log) == 0:
        return

    report = {}
    order = []
    for entry in log:
        name = entry["provider"]
        if name not in report:
            line = {}
            line["calls"] = 0
            line["answered"] = 0
            line["problems"] = {}
            line["answer_seconds"] = []
            line["waited_seconds"] = 0.0
            report[name] = line
            order.append(name)
        line = report[name]
        line["calls"] = line["calls"] + 1
        line["waited_seconds"] = line["waited_seconds"] + entry["seconds"]
        if entry["outcome"] == "answered":
            line["answered"] = line["answered"] + 1
            line["answer_seconds"].append(entry["seconds"])
        else:
            outcome = entry["outcome"]
            line["problems"][outcome] = line["problems"].get(outcome, 0) + 1

    rows = []
    for name in order:
        line = report[name]
        average = ""
        if len(line["answer_seconds"]) > 0:
            average = str(round(sum(line["answer_seconds"]) / len(line["answer_seconds"]), 1)) + " s"
        problems = []
        for outcome in line["problems"]:
            problems.append(str(line["problems"][outcome]) + "× " + outcome)
        table_row = {}
        table_row["Engine"] = name
        table_row["Calls"] = line["calls"]
        table_row["Answered"] = line["answered"]
        table_row["Avg answer"] = average
        table_row["Problems"] = ", ".join(problems) if problems else "none"
        rows.append(table_row)

    st.dataframe(pd.DataFrame(rows), hide_index=True)
    st.caption("If an engine is slower than " + str(HEDGE_SECONDS) + " s, the next one races it.")


def show_evidence(row, pdfs):
    left, right = st.columns([2, 3], gap="large")

    with left:
        st.markdown(ui.evidence_card(row), unsafe_allow_html=True)

    with right:
        pdf_bytes = pdfs.get(row["paper"])
        if "evidence not found" in row["checks"]:
            # dont highlight anything: the sentence the ai quoted isn't in the paper
            st.error("The quoted evidence isn't in this paper, so there's nothing to highlight.")
            return
        if pdf_bytes is None or pd.isna(row["page"]):
            st.info("No page to show for this row.")
            return
        image, how = render_evidence(pdf_bytes, int(row["page"]), row["evidence"], row["value"])
        if image is None or how == "not found":
            st.info("Couldn't locate the text on the page to highlight it.")
            if image is not None:
                st.image(image, width="stretch")
            return
        st.image(image, width="stretch")


def show_accuracy(rows, key):
    with st.expander("Check accuracy against an answer key"):
        st.caption("Upload a CSV with columns material, property, value.")
        template = pd.DataFrame([{"paper": "", "material": "", "property": "", "value": "", "unit": "", "page": ""}])
        st.download_button("Blank answer key", data=template.to_csv(index=False), file_name="answer_key_template.csv",
                           mime="text/csv", key="template_" + key)
        key_file = st.file_uploader("Answer key", type=["csv"], key="answer_key_" + key, label_visibility="collapsed")
        if key_file is None:
            return
        try:
            answers = read_answer_key(pd.read_csv(key_file))
        except Exception as error:
            st.error(str(error))
            return

        report = evaluate(rows, answers)
        columns = st.columns(3)
        columns[0].metric("Precision", str(round(report["precision"] * 100)) + "%",
                          help="Of the values Datum extracted, how many were right")
        columns[1].metric("Recall", str(round(report["recall"] * 100)) + "%",
                          help="Of the true values in the answer key, how many Datum found")
        columns[2].metric("Errors caught", str(report["wrong_caught"]) + " / " + str(report["wrong"]),
                          help="Of Datum's wrong values, how many verification already marked review or flagged")
        if len(report["missed"]) > 0:
            st.caption("Missed")
            st.dataframe(pd.DataFrame(report["missed"]), hide_index=True)


def show_results(result, key, pdfs):
    rows = result["rows"]
    stats = result["stats"]

    if len(rows) == 0:
        st.info("None of these properties were found in the papers. Try other wording, or turn on Scan every page in Settings.")
        return

    left, right = st.columns([4, 1], vertical_alignment="center")
    with left:
        st.markdown(ui.summary(rows, stats), unsafe_allow_html=True)

    table = pd.DataFrame(rows)
    table["row_id"] = range(len(table))
    table["page"] = pd.to_numeric(table["page"], errors="coerce").astype("Int64")
    export = table.drop(columns=["row_id"])
    with right:
        st.download_button("CSV", data=export.to_csv(index=False), file_name="datum_dataset.csv",
                           mime="text/csv", type="primary", key="csv_" + key, icon=":material/download:", width="stretch")

    choice = st.segmented_control("Show", list(FILTERS.keys()), default="All", key="filter_" + key, label_visibility="collapsed")
    chosen = FILTERS.get(choice or "All")
    view = table[table["status"].isin(chosen)].reset_index(drop=True)
    screen = view.copy()
    screen["status"] = screen["status"].map(STATUS_LABELS)

    event = st.dataframe(
        screen,
        column_order=SCREEN_COLUMNS,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="table_" + key,
        column_config={
            "status": st.column_config.TextColumn("Status", width="small"),
            "property_std": st.column_config.TextColumn("Property"),
            "property": st.column_config.TextColumn("As written"),
            "origin": st.column_config.TextColumn("Origin"),
            "reference": st.column_config.TextColumn("Ref", width="small"),
            "value_std": st.column_config.TextColumn("Std value"),
            "unit_std": st.column_config.TextColumn("Std unit"),
            "page": st.column_config.NumberColumn("Page", format="%d"),
            "checks": st.column_config.TextColumn("Checks", width="large"),
        },
    )

    selected = event.selection.rows if event is not None else []
    if len(selected) > 0:
        row_id = int(view.iloc[selected[0]]["row_id"])
        show_evidence(table[table["row_id"] == row_id].iloc[0], pdfs)
    else:
        st.caption("Select a row to see where it came from.")

    with st.expander("Details"):
        show_engine_report(stats)
        for name in stats["disabled_providers"]:
            st.caption(name + " was switched off this run: " + stats["disabled_providers"][name][:160])
        if len(result["failures"]) > 0:
            st.dataframe(pd.DataFrame(result["failures"]), hide_index=True)
    show_accuracy(rows, key)


# ---------------------------------------------------------
# the pipeline view: five real stages, one sliding glass capsule
# ---------------------------------------------------------
def stage_states(index, failed=False):
    states = []
    for position in range(len(pipeline.STAGES)):
        if position < index:
            states.append("done")
        elif position == index:
            states.append("failed" if failed else "active")
        else:
            states.append("todo")
    return states


def completed_pipeline(result):
    # compact, finished state shown above the results
    if len(result["failures"]) > 0:
        status = str(len(result["failures"])) + " part(s) couldn't be extracted. Retry to try them again; finished papers load instantly."
        return ui.pipeline(stage_states(2, failed=True), 2, 2, status, compact=True)
    states = ["done", "done", "done", "done", "done"]
    return ui.pipeline(states, None, None, "", compact=True)


def run_extraction(thread, settings):
    placeholder = st.empty()
    position = {"current": None}

    def on_stage(name, detail):
        index = pipeline.STAGES.index(name)
        previous = position["current"] if position["current"] is not None else index
        placeholder.markdown(ui.pipeline(stage_states(index), index, previous, detail), unsafe_allow_html=True)
        position["current"] = index

    placeholder.markdown(ui.pipeline(stage_states(0), 0, 0, "Starting"), unsafe_allow_html=True)

    pdfs = threads.paper_bytes(thread)
    papers = []
    for name in pdfs:
        paper = {}
        paper["name"] = name
        paper["bytes"] = pdfs[name]
        papers.append(paper)

    try:
        result = pipeline.run(
            papers,
            thread["properties"],
            settings["providers"],
            workers=settings["workers"],
            filter_pages=not settings["scan_all"],
            use_cache=settings["use_cache"],
            on_stage=on_stage,
        )
    except Exception as error:
        # keep the failed stage visible and say what happened
        index = position["current"] if position["current"] is not None else 0
        message = "Stopped at " + ui.STAGE_LABELS[index] + ": " + str(error)[:160]
        st.session_state["run_error_" + thread["id"]] = {"index": index, "message": message}
        return

    st.session_state.pop("run_error_" + thread["id"], None)
    threads.add_run(thread, thread["properties"], list(pdfs.keys()), result)
    threads.save(thread)
    st.rerun()


def pick_suggestions(thread_id, pills_key, names):
    # a chip was toggled: rewrite the properties box to match
    thread = threads.load(thread_id, st.session_state.get("space", ""))
    if thread is None:
        return
    props_key = "props_" + thread_id
    before = st.session_state.get(props_key, thread.get("properties", ""))
    after = suggest.apply_selection(before, names, st.session_state.get(pills_key) or [])
    st.session_state[props_key] = after
    thread["properties"] = after
    threads.save(thread)


def suggestion_label(item, paper_count):
    label = item["name"]
    if item.get("unit"):
        label = label + "  ·  " + item["unit"]
    if paper_count > 1 and len(item["papers"]) > 1:
        label = label + "  ·  " + str(len(item["papers"])) + " papers"
    return label


def show_suggestions(thread, providers, use_cache):
    # "what do these papers report?" - chips the researcher can click into the properties box
    if len(thread["papers"]) == 0:
        return
    paper_names = [paper["name"] for paper in thread["papers"]]
    saved = thread.get("suggestions")
    stale = saved is None or sorted(saved.get("papers", [])) != sorted(paper_names)

    if saved and len(saved.get("items", [])) > 0:
        items = {}
        for item in saved["items"]:
            items[item["name"]] = item
        names = list(items.keys())
        props_text = st.session_state.get("props_" + thread["id"], thread.get("properties", ""))
        pills_key = "pick_" + thread["id"] + "_" + str(zlib.crc32(props_text.encode("utf-8")))
        st.pills("Reported in your papers", names, selection_mode="multi",
                 default=suggest.selected_in(props_text, names),
                 format_func=lambda name: suggestion_label(items[name], len(paper_names)),
                 key=pills_key, on_change=pick_suggestions, args=(thread["id"], pills_key, names))
    elif saved and not stale and len(saved.get("failures", [])) == 0:
        st.caption("No measured properties found in the abstract or tables. Type your own above.")

    if saved and len(saved.get("failures", [])) > 0:
        st.caption("Couldn't read every paper for suggestions: " + saved["failures"][0])

    if stale and len(providers) > 0:
        # runs on its own as soon as the papers change - one cached call per paper
        with st.spinner("Reading your papers for the properties they report…"):
            thread["suggestions"] = suggest.suggest(threads.paper_bytes(thread), providers, use_cache)
        threads.save(thread)
        st.rerun()
    if saved and not stale and len(saved.get("failures", [])) > 0:
        if st.button("Try suggestions again", key="suggest_again_" + thread["id"], icon=":material/refresh:", type="tertiary"):
            thread["suggestions"] = None
            threads.save(thread)
            st.rerun()


# ---------------------------------------------------------
# which thread is open
# ---------------------------------------------------------
providers, provider_notes = build_providers(get_secret)

space = pick_space()
all_threads = threads.list_threads(space)
current = None
if st.session_state.get("thread_id"):
    current = threads.load(st.session_state["thread_id"], space)
if current is None:
    if len(all_threads) > 0:
        # open the most recent thread that has work in it, not an empty one
        current = all_threads[0]
        for thread in all_threads:
            if len(thread["papers"]) > 0 or len(thread["runs"]) > 0:
                current = thread
                break
    else:
        current = threads.new_thread(space)
        all_threads = [current]
    st.session_state["thread_id"] = current["id"]

# ---------------------------------------------------------
# sidebar: threads, then settings
# ---------------------------------------------------------
with st.sidebar:
    st.markdown(ui.sidebar_mark(LANDING_URL), unsafe_allow_html=True)

    if st.button("New thread", key="new_thread", icon=":material/edit_square:", width="stretch"):
        empty = len(current["papers"]) == 0 and len(current["runs"]) == 0
        if not empty:
            fresh = threads.new_thread(space)
            st.session_state["thread_id"] = fresh["id"]
        st.rerun()

    st.markdown(ui.side_label("Threads"), unsafe_allow_html=True)
    for thread in all_threads:
        is_open = thread["id"] == current["id"]
        name_column, menu_column = st.columns([6, 1])
        with name_column:
            if st.button(thread["title"], key="open_" + thread["id"], width="stretch",
                         type="primary" if is_open else "secondary"):
                st.session_state["thread_id"] = thread["id"]
                st.rerun()
        with menu_column:
            with st.popover("", icon=":material/more_horiz:"):
                # the key includes the current title, so the box always starts from the real name
                # (a fixed key would remember an old name and write it back)
                title_tag = str(zlib.crc32(thread["title"].encode("utf-8")))
                new_title = st.text_input("Rename", value=thread["title"], key="rename_" + thread["id"] + "_" + title_tag)
                if new_title.strip() != "" and new_title != thread["title"]:
                    threads.rename(thread, new_title)
                    threads.save(thread)
                    st.rerun()
                if st.button("Delete thread", key="delete_" + thread["id"], icon=":material/delete:"):
                    threads.delete(thread["id"], space)
                    if is_open:
                        st.session_state["thread_id"] = None
                    st.rerun()

    st.markdown(ui.side_label("Settings"), unsafe_allow_html=True)
    with st.popover("Engines and options", icon=":material/tune:", width="stretch"):
        if len(providers) == 0:
            st.error("No engine set up. Add an API key to .streamlit/secrets.toml.")
        for provider in providers:
            st.markdown("● " + provider["name"] + " · " + provider["model"])
        for note in provider_notes:
            st.caption("○ " + note)
        workers = st.slider("Parallel requests", min_value=1, max_value=8, value=pipeline.DEFAULT_WORKERS, key="workers")
        scan_all = st.toggle("Scan every page", value=False, key="scan_all",
                             help="Slower. Use it if a paper words things differently from your properties.")
        use_cache = st.toggle("Reuse earlier results", value=True, key="use_cache")

    if space != "":
        st.markdown(ui.side_note("Your threads are private to this link. Bookmark it to come back."), unsafe_allow_html=True)
    st.markdown(ui.side_link("About Datum", LANDING_URL), unsafe_allow_html=True)

settings = {}
settings["providers"] = providers
settings["workers"] = workers
settings["scan_all"] = scan_all
settings["use_cache"] = use_cache

# ---------------------------------------------------------
# the workspace
# ---------------------------------------------------------
st.markdown(ui.thread_header(current["title"], len(current["papers"])), unsafe_allow_html=True)

with st.container(key="composer"):
    props_key = "props_" + current["id"]
    if props_key not in st.session_state or st.session_state.pop("sync_props_" + current["id"], False):
        st.session_state[props_key] = current.get("properties", "")
    has_suggestions = bool((current.get("suggestions") or {}).get("items"))
    properties = st.text_input("Properties", key=props_key,
                               placeholder=("Leave empty to extract everything reported below, or pick some"
                                            if has_suggestions else
                                            "e.g. μC*, volumetric capacitance C* — or leave empty to extract everything"))
    if properties != current.get("properties", ""):
        current["properties"] = properties
        threads.save(current)

    show_suggestions(current, providers, use_cache)

    st.markdown('<div class="dt-files-label">Papers</div>', unsafe_allow_html=True)
    for index in range(len(current["papers"])):
        paper = current["papers"][index]
        with st.container(key="paper_" + current["id"] + "_" + str(index)):
            name_column, remove_column = st.columns([14, 1], vertical_alignment="center")
            with name_column:
                st.markdown(ui.file_item(paper["name"], paper.get("size", 0)), unsafe_allow_html=True)
            with remove_column:
                if st.button("", key="remove_" + current["id"] + "_" + str(index), icon=":material/close:", help="Remove"):
                    threads.remove_paper(current, paper["name"])
                    threads.save(current)
                    st.rerun()

    # the uploader is reset after every upload, so files live in the thread, not the widget
    upload_round = st.session_state.get("upload_round_" + current["id"], 0)
    uploads = st.file_uploader("Add PDFs", type=["pdf"], accept_multiple_files=True,
                               key="upload_" + current["id"] + "_" + str(upload_round), label_visibility="collapsed")
    if uploads:
        for upload in uploads:
            threads.add_paper(current, upload.name, upload.getvalue())
        threads.save(current)
        st.session_state["upload_round_" + current["id"]] = upload_round + 1
        st.rerun()

    ready = len(current["papers"]) > 0 and len(providers) > 0
    spacer, button_column = st.columns([4, 1])
    with button_column:
        label = "Extract" if properties.strip() != "" else "Extract all"
        extract = st.button(label, type="primary", disabled=not ready, key="extract_" + current["id"], width="stretch")

    if extract and properties.strip() == "":
        # nothing typed: extract every property the papers were found to report
        found = current.get("suggestions") or {}
        if sorted(found.get("papers", [])) != sorted(p["name"] for p in current["papers"]):
            with st.spinner("Reading your papers for the properties they report…"):
                found = suggest.suggest(threads.paper_bytes(current), providers, use_cache)
            current["suggestions"] = found
        names = [item["name"] for item in found.get("items", [])]
        extract = False
        if len(names) == 0:
            st.caption("Datum couldn't find reported properties in the abstract or tables. Type the ones you want above.")
        else:
            current["properties"] = ", ".join(names)
            st.session_state["sync_props_" + current["id"]] = True    # show what we used in the box
            st.session_state["autorun_" + current["id"]] = True
        threads.save(current)
        if len(names) > 0:
            st.rerun()

    if st.session_state.pop("autorun_" + current["id"], False):
        extract = True

error = st.session_state.get("run_error_" + current["id"])

if extract:
    run_extraction(current, settings)
    error = st.session_state.get("run_error_" + current["id"])

if error is not None:
    st.markdown(ui.pipeline(stage_states(error["index"], failed=True), error["index"], error["index"], error["message"]),
                unsafe_allow_html=True)
    if st.button("Retry", icon=":material/refresh:", key="retry_" + current["id"]):
        st.session_state.pop("run_error_" + current["id"], None)
        run_extraction(current, settings)
elif len(current["runs"]) > 0:
    latest = current["runs"][-1]
    st.markdown(completed_pipeline(latest["result"]), unsafe_allow_html=True)
    if len(latest["result"]["failures"]) > 0:
        if st.button("Retry", icon=":material/refresh:", key="retry_failed_" + current["id"]):
            run_extraction(current, settings)
    show_results(latest["result"], current["id"] + "_" + str(len(current["runs"])), threads.paper_bytes(current))
