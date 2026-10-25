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

st.set_page_config(page_title="Datum", page_icon="◆", layout="wide")

DEFAULT_PROPERTIES = "μC*, volumetric capacitance C*, electrical conductivity"

STATUS_LABELS = {
    STATUS_VERIFIED: "✅ verified",
    STATUS_REVIEW: "🟡 review",
    STATUS_FLAGGED: "🚩 flagged",
}

# columns shown in the on-screen table (the csv download has all of them)
SCREEN_COLUMNS = [
    "status", "material", "property_std", "property", "value", "error", "unit",
    "value_std", "unit_std", "origin", "paper", "page", "checks",
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

    with st.expander("Engine report: where the time went", expanded=open_it):
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        st.caption(
            "Calls run in parallel, so total time per engine can be larger than the run time. "
            "If one engine is slower than " + str(HEDGE_SECONDS) + " s, the next engine races it."
        )


def show_stats(result):
    rows = result["rows"]
    stats = result["stats"]

    counts = {STATUS_VERIFIED: 0, STATUS_REVIEW: 0, STATUS_FLAGGED: 0}
    for row in rows:
        counts[row["status"]] = counts[row["status"]] + 1

    columns = st.columns(6)
    columns[0].metric("Papers", stats["papers"])
    columns[1].metric("Measurements", len(rows))
    columns[2].metric("Verified", counts[STATUS_VERIFIED])
    columns[3].metric("Needs review", counts[STATUS_REVIEW])
    columns[4].metric("Flagged", counts[STATUS_FLAGGED])
    columns[5].metric("Time", str(stats["seconds"]) + " s")

    calls = []
    for name in stats["calls_by_provider"]:
        calls.append(name + " " + str(stats["calls_by_provider"][name]))
    details = (
        str(stats["pages_sent"]) + " of " + str(stats["pages_total"]) + " pages sent to the AI · "
        + str(stats["papers_from_cache"]) + " paper(s) reused from earlier runs · "
        + "AI calls: " + (", ".join(calls) if calls else "none")
    )
    st.caption(details)

    show_engine_report(stats, open_it=len(result["failures"]) > 0)

    if len(stats["disabled_providers"]) > 0:
        for name in stats["disabled_providers"]:
            st.info(name + " was switched off this run: " + stats["disabled_providers"][name][:200])

    if len(result["failures"]) > 0:
        st.warning(
            str(len(result["failures"])) + " part(s) of the papers could not be read by any AI provider. "
            + "Everything else is below. Press Extract again to retry just those parts "
            + "(finished papers are reused instantly)."
        )
        with st.expander("What failed"):
            st.dataframe(pd.DataFrame(result["failures"]), hide_index=True)


def show_evidence(row):
    st.subheader(row["material"] + " · " + row["property"])
    left, right = st.columns([2, 3])

    with left:
        value_text = row["value"]
        if row["error"]:
            value_text = value_text + " ± " + row["error"]
        st.markdown("**Value:** " + value_text + " " + row["unit"])
        if row["value_std"] and row["unit_std"] != row["unit"]:
            st.markdown("**Standard unit:** " + row["value_std"] + " " + row["unit_std"])
        st.markdown("**Status:** " + STATUS_LABELS[row["status"]])
        st.markdown("**Evidence** (page " + str(row["page"]) + " of " + row["paper"] + "):")
        st.code(row["evidence"], language=None, wrap_lines=True)
        if row["conditions"]:
            st.markdown("**Conditions:** " + row["conditions"])
        if row["checks"]:
            st.markdown("**Checks:**")
            for check in row["checks"].split("; "):
                st.markdown("- " + check)
        st.caption("Extracted by " + row["provider"])

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
            st.caption("Highlighted by value (the full sentence wraps oddly in this PDF).")
        else:
            st.caption("Highlighted straight from the PDF.")


def show_accuracy(rows):
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
        )
        key_file = st.file_uploader("Answer key (CSV)", type=["csv"], key="answer_key")
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
            st.dataframe(pd.DataFrame(report["missed"]), hide_index=True)


def show_results(result):
    show_stats(result)
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
        key="results_table",
        column_config={
            "status": st.column_config.TextColumn("Status", width="small"),
            "property_std": st.column_config.TextColumn("Target property"),
            "property": st.column_config.TextColumn("As written"),
            "origin": st.column_config.TextColumn("Origin"),
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
        st.caption("Select a row to see exactly where the number came from.")

    export = table.drop(columns=["row_id"])
    st.download_button(
        "Download CSV (all rows)",
        data=export.to_csv(index=False),
        file_name="datum_dataset.csv",
        mime="text/csv",
        type="primary",
    )

    show_accuracy(rows)


# ---------------------------------------------------------
# the page
# ---------------------------------------------------------
providers, provider_notes = build_providers(get_secret)

with st.sidebar:
    st.header("Engines")
    if len(providers) == 0:
        st.error("No AI provider set up. Add at least one key: CEREBRAS_API_KEY, GEMINI_API_KEY, GROQ_API_KEY, ANTHROPIC_API_KEY or OPENAI_API_KEY.")
    for provider in providers:
        st.markdown("● **" + provider["name"] + "** · " + provider["model"])
    for note in provider_notes:
        st.caption("○ " + note)
    st.caption("If one engine is busy, Datum automatically hops to the next.")

    st.divider()
    workers = st.slider(
        "Parallel requests", min_value=1, max_value=8, value=pipeline.DEFAULT_WORKERS,
        help="How many AI calls run at the same time. Lower it if you hit rate limits.",
    )
    scan_all = st.toggle(
        "Scan every page", value=False,
        help="Slower. Use it if Datum misses values because a paper uses different wording.",
    )
    use_cache = st.toggle(
        "Reuse earlier results", value=True,
        help="Papers you already ran (with the same properties) load instantly.",
    )

st.title("Datum")
st.caption("Turn materials papers into a dataset where every number traces back to its source.")

properties = st.text_input("Properties to extract", value=DEFAULT_PROPERTIES)
uploads = st.file_uploader("Papers (PDF)", type=["pdf"], accept_multiple_files=True)

ready = len(providers) > 0 and uploads is not None and len(uploads) > 0 and properties.strip() != ""
if st.button("Extract", type="primary", disabled=not ready):
    papers = []
    for upload in uploads:
        paper = {}
        paper["name"] = upload.name
        paper["bytes"] = upload.getvalue()
        papers.append(paper)

    progress = st.progress(0.0, text="Reading papers…")

    def on_progress(done, total, message):
        if total == 0:
            progress.progress(1.0, text="Everything reused from earlier runs")
            return
        progress.progress(done / total, text=str(done) + " / " + str(total) + " · " + message)

    result = pipeline.run(
        papers,
        properties,
        providers,
        workers=workers,
        filter_pages=not scan_all,
        use_cache=use_cache,
        on_progress=on_progress,
    )
    progress.empty()

    pdfs = {}
    for paper in papers:
        pdfs[paper["name"]] = paper["bytes"]
    st.session_state["result"] = result
    st.session_state["pdfs"] = pdfs

if "result" in st.session_state:
    show_results(st.session_state["result"])
