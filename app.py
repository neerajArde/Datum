# app.py
# the screen. this file ONLY does user interface - all the real work
# lives in pipeline.py and the modules it calls. that way a ui change
# can never break extraction, and an extraction fix never breaks the ui.
#
# run with:  python -m streamlit run app.py

import os

import pandas as pd
import streamlit as st

import pipeline
from evaluate import evaluate, read_answer_key
from highlight import render_evidence
from providers import HEDGE_SECONDS, build_providers
from schema import STATUS_FLAGGED, STATUS_REVIEW, STATUS_VERIFIED
import threads
import ui

st.set_page_config(page_title="Datum", page_icon="◆", layout="wide", initial_sidebar_state="expanded")
st.markdown(ui.CSS, unsafe_allow_html=True)

DEFAULT_PROPERTIES = "μC*, volumetric capacitance C*, electrical conductivity"

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
    return ""


# ---------------------------------------------------------
# results: the table, the evidence viewer, accuracy, download
# ---------------------------------------------------------
def show_engine_report(stats, open_it):
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
            line["engine"] = name
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
        table_row["Avg answer time"] = average
        table_row["Problems"] = ", ".join(problems) if problems else "none"
        table_row["Total time spent"] = str(round(line["waited_seconds"], 1)) + " s"
        rows.append(table_row)

    if open_it:
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        st.caption(
            "Calls run in parallel, so total time per engine can be larger than the run time. "
            "If one engine is slower than " + str(HEDGE_SECONDS) + " s, the next engine races it."
        )


def show_stats(result, key):
    rows = result["rows"]
    stats = result["stats"]

    st.markdown(ui.trust_bar(rows, stats), unsafe_allow_html=True)

    if len(result["failures"]) > 0:
        st.warning(
            str(len(result["failures"])) + " part(s) couldn't be read by any engine. "
            + "Send the same request again to retry them. Finished papers load instantly."
        )

    with st.expander("Details", expanded=False):
        calls = []
        for name in stats["calls_by_provider"]:
            if stats["calls_by_provider"][name] > 0:
                calls.append(name + " " + str(stats["calls_by_provider"][name]))
        if len(calls) > 0:
            st.caption("Answered by: " + ", ".join(calls))
        show_engine_report(stats, open_it=True)
        for name in stats["disabled_providers"]:
            st.caption(name + " was switched off this run: " + stats["disabled_providers"][name][:160])
        if len(result["failures"]) > 0:
            st.dataframe(pd.DataFrame(result["failures"]), hide_index=True, key="failures_" + key)


def show_evidence(row):
    left, right = st.columns([2, 3], gap="large")

    with left:
        st.markdown(ui.evidence_card(row), unsafe_allow_html=True)
        st.caption("Extracted by " + str(row["provider"]) + ", checked by Datum against the PDF.")

    with right:
        pdfs = st.session_state.get("pdfs", {})
        pdf_bytes = pdfs.get(row["paper"])
        if "evidence not found" in row["checks"]:
            # dont highlight anything: the sentence the ai quoted isn't in the paper
            st.error("The quoted evidence does not exist anywhere in this paper, so there is nothing to highlight.")
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
        if how == "value only":
            st.caption("The value is highlighted on the page. The full quote wraps across lines in this PDF.")
        else:
            st.caption("The quote, highlighted on the original page.")


def show_accuracy(rows, key):
    with st.expander("Check accuracy against an answer key"):
        st.write(
            "Upload a CSV with the true values for these papers (columns: material, property, value). "
            "Datum compares its table against it."
        )
        template = pd.DataFrame([{"paper": "", "material": "", "property": "", "value": "", "unit": "", "page": ""}])
        st.download_button(
            "Download blank answer key",
            data=template.to_csv(index=False),
            file_name="answer_key_template.csv",
            mime="text/csv",
            key="template_" + key,
        )
        key_file = st.file_uploader("Answer key (CSV)", type=["csv"], key="answer_key_" + key)
        if key_file is None:
            return
        try:
            answers = read_answer_key(pd.read_csv(key_file))
        except Exception as error:
            st.error(str(error))
            return

        report = evaluate(rows, answers)
        columns = st.columns(3)
        columns[0].metric(
            "Precision", str(round(report["precision"] * 100)) + "%",
            help="Of the values Datum extracted, how many were right",
        )
        columns[1].metric(
            "Recall", str(round(report["recall"] * 100)) + "%",
            help="Of the true values in the answer key, how many Datum found",
        )
        columns[2].metric(
            "Errors caught", str(report["wrong_caught"]) + " / " + str(report["wrong"]),
            help="Of Datum's wrong values, how many verification already marked review or flagged",
        )
        st.caption(
            str(report["correct"]) + " correct out of " + str(report["extracted"]) + " extracted · "
            + str(report["found"]) + " of " + str(report["answer_key_size"]) + " answer-key values found"
        )
        if len(report["missed"]) > 0:
            st.markdown("**Values Datum missed:**")
            st.dataframe(pd.DataFrame(report["missed"]), hide_index=True, key="missed_" + key)


def show_results(result, key):
    show_stats(result, key)
    rows = result["rows"]

    if len(rows) == 0:
        st.info("No target properties were found in these papers.")
        return

    table = pd.DataFrame(rows)
    table["row_id"] = range(len(table))
    table["page"] = pd.to_numeric(table["page"], errors="coerce").astype("Int64")

    chosen = st.multiselect(
        "Show",
        options=[STATUS_VERIFIED, STATUS_REVIEW, STATUS_FLAGGED],
        default=[STATUS_VERIFIED, STATUS_REVIEW, STATUS_FLAGGED],
        format_func=lambda status: STATUS_LABELS[status],
        key="show_" + key,
        label_visibility="collapsed",
    )
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
            "property_std": st.column_config.TextColumn("Target property"),
            "property": st.column_config.TextColumn("As written"),
            "origin": st.column_config.TextColumn("Origin"),
            "reference": st.column_config.TextColumn("Ref #", width="small"),
            "value_std": st.column_config.TextColumn("Std value"),
            "unit_std": st.column_config.TextColumn("Std unit"),
            "page": st.column_config.NumberColumn("Page", format="%d"),
            "checks": st.column_config.TextColumn("Checks", width="large"),
        },
    )

    selected = event.selection.rows if event is not None else []
    if len(selected) > 0:
        row_id = int(view.iloc[selected[0]]["row_id"])
        show_evidence(table[table["row_id"] == row_id].iloc[0])
    else:
        st.caption("Tick a row to see where it came from.")

    export = table.drop(columns=["row_id"])
    st.download_button(
        "Download CSV",
        data=export.to_csv(index=False),
        file_name="datum_dataset.csv",
        mime="text/csv",
        type="primary",
        key="csv_" + key,
    )

    show_accuracy(rows, key)


# ---------------------------------------------------------
# the page: a thread list on the left, one thread on the right
# ---------------------------------------------------------
providers, provider_notes = build_providers(get_secret)

all_threads = threads.list_threads()
if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = all_threads[0]["id"] if len(all_threads) > 0 else None

current = None
if st.session_state["thread_id"] is not None:
    current = threads.load(st.session_state["thread_id"])

with st.sidebar:
    st.markdown(ui.sidebar_mark(), unsafe_allow_html=True)
    if st.button("New thread", key="new_thread", icon=":material/add:", width="stretch"):
        st.session_state["thread_id"] = None
        st.rerun()

    for thread in all_threads:
        is_open = current is not None and thread["id"] == current["id"]
        if st.button(thread["title"], key="open_" + thread["id"], width="stretch",
                     type="primary" if is_open else "secondary"):
            st.session_state["thread_id"] = thread["id"]
            st.rerun()

    st.markdown('<div class="dt-sidebar-spacer"></div>', unsafe_allow_html=True)
    with st.popover("Settings", icon=":material/tune:", width="stretch"):
        st.markdown("**Engines**")
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
        if current is not None:
            new_title = st.text_input("Thread name", value=current["title"], key="title_" + current["id"])
            if new_title != current["title"]:
                threads.rename(current, new_title)
                threads.save(current)
                st.rerun()

# ---- the open thread (or an empty start screen)
if current is None or len(current["runs"]) == 0:
    st.markdown(ui.empty_state(), unsafe_allow_html=True)
else:
    st.session_state["pdfs"] = threads.paper_bytes(current)
    total_runs = len(current["runs"])
    for index in range(total_runs):
        run = current["runs"][index]
        st.markdown(ui.request_bubble(run["properties"], run["papers"]), unsafe_allow_html=True)
        key = current["id"] + "_" + str(index)
        if index < total_runs - 1:
            # earlier runs fold away so the latest one gets the space
            with st.expander(ui.run_summary(run["result"]), expanded=False):
                show_results(run["result"], key)
        else:
            show_results(run["result"], key)

# ---- the input bar: properties as text, pdfs as attachments
last_properties = ""
if current is not None and len(current["runs"]) > 0:
    last_properties = current["runs"][-1]["properties"]

placeholder = "Properties to extract, e.g. μC*, volumetric capacitance C*"
if current is not None and len(current["papers"]) > 0:
    placeholder = "Ask for other properties from these papers, or attach more"

submitted = st.chat_input(placeholder, accept_file="multiple", file_type=["pdf"], key="composer")

if submitted:
    properties = (submitted.text or "").strip() or last_properties
    files = submitted.files or []

    if properties == "":
        st.toast("Type the properties you want, e.g. μC*, volumetric capacitance C*", icon=":material/info:")
    elif len(files) == 0 and (current is None or len(current["papers"]) == 0):
        st.toast("Attach at least one PDF with the paperclip.", icon=":material/attach_file:")
    elif len(providers) == 0:
        st.toast("No engine set up. Add an API key in Settings.", icon=":material/error:")
    else:
        if current is None:
            current = threads.new_thread()
            st.session_state["thread_id"] = current["id"]
        for upload in files:
            threads.add_paper(current, upload.name, upload.getvalue())
        threads.save(current)

        pdfs = threads.paper_bytes(current)
        papers = []
        for name in pdfs:
            paper = {}
            paper["name"] = name
            paper["bytes"] = pdfs[name]
            papers.append(paper)

        with st.status("Reading " + str(len(papers)) + (" paper" if len(papers) == 1 else " papers") + "…", expanded=False) as status:
            progress = st.progress(0.0)

            def on_progress(done, total, message):
                if total == 0:
                    progress.progress(1.0)
                    return
                progress.progress(done / total)
                status.update(label=str(done) + " of " + str(total) + " parts read · " + message)

            result = pipeline.run(
                papers,
                properties,
                providers,
                workers=workers,
                filter_pages=not scan_all,
                use_cache=use_cache,
                on_progress=on_progress,
            )
            status.update(label="Done", state="complete")

        threads.add_run(current, properties, list(pdfs.keys()), result)
        threads.save(current)
        st.rerun()
