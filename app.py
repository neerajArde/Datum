# datum - team ground truth - hackpsu fall 2026
# idea: researcher uploads papers + says which properties they care about
# llm reads each page and pulls out measurements
# then plain code checks the llm didnt make stuff up (hallucinations)

import os
import json

import streamlit as st
import pandas as pd
import fitz  # this is pymupdf, it reads pdfs page by page
from google import genai
from rapidfuzz import fuzz


# swap this if theres a newer gemini model available
MODEL_NAME = "gemini-2.5-flash"


# ---------------------------------------------------------
# step 0: get the api key
# ---------------------------------------------------------
def get_api_key():
    # first try streamlit secrets (this is how it works when deployed)
    try:
        key = st.secrets["GEMINI_API_KEY"]
        return key
    except Exception:
        pass

    # if that didnt work, try a normal environment variable (local testing)
    key = os.environ.get("GEMINI_API_KEY")
    return key


# ---------------------------------------------------------
# step 1: read the pdf and keep page numbers
# ---------------------------------------------------------
def read_pdf_pages(uploaded_file):
    # streamlit gives us the file, we turn it into raw bytes
    pdf_bytes = uploaded_file.read()

    # open the pdf from those bytes
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    pages = []
    page_number = 1

    for page in doc:
        page_text = page.get_text()

        # build the dict key by key so i can see whats in it
        page_info = {}
        page_info["page"] = page_number
        page_info["text"] = page_text

        pages.append(page_info)
        page_number = page_number + 1

    return pages


# ---------------------------------------------------------
# step 2: ask the llm to pull out measurements from ONE page
# ---------------------------------------------------------
def build_prompt(page_text, target_properties):
    # this is the "extraction schema" - the researcher tells us what to look for
    prompt = ""
    prompt = prompt + "You are extracting measurements from a materials science paper.\n"
    prompt = prompt + "Only extract these properties: " + target_properties + "\n"
    prompt = prompt + "Ignore every other number on the page.\n"
    prompt = prompt + "Return a JSON list. Each item must have these keys:\n"
    prompt = prompt + "  material: the material name exactly as written in the paper\n"
    prompt = prompt + "  property: which target property this is\n"
    prompt = prompt + "  value: the number only, as a string (example: \"490\")\n"
    prompt = prompt + "  error: the +/- value as a string, or \"\" if there is none\n"
    prompt = prompt + "  unit: the unit exactly as written\n"
    prompt = prompt + "  evidence: copy the exact sentence or table row from the page, word for word\n"
    prompt = prompt + "  conditions: processing or testing conditions mentioned (electrolyte, thickness, etc), or \"\"\n"
    prompt = prompt + "If the page has none of the target properties, return an empty list [].\n"
    prompt = prompt + "Never guess. Never invent values.\n\n"
    prompt = prompt + "PAGE TEXT:\n"
    prompt = prompt + page_text
    return prompt


def extract_from_page(client, page_text, target_properties):
    prompt = build_prompt(page_text, target_properties)

    # ask gemini to answer in json mode so we dont get broken json at 3am
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config={"response_mime_type": "application/json"},
    )

    # try to turn the text into a python list
    try:
        rows = json.loads(response.text)
    except Exception:
        # if the llm messed up the json, just skip this page
        rows = []

    # sometimes it returns a single dict instead of a list
    if isinstance(rows, dict):
        rows = [rows]

    if not isinstance(rows, list):
        rows = []

    return rows


# ---------------------------------------------------------
# step 3: verification - plain code, NOT the llm
# ---------------------------------------------------------
def clean_text(text):
    # pdfs have weird spacing and line breaks, so squash all whitespace
    if text is None:
        return ""
    text = str(text)
    words = text.split()
    cleaned = " ".join(words)
    return cleaned.lower()


def verify_row(row, page_text):
    flags = []

    evidence = clean_text(row.get("evidence", ""))
    page = clean_text(page_text)
    value = clean_text(row.get("value", ""))

    # check 1: does the evidence actually exist on this page?
    if evidence == "":
        flags.append("no evidence given")
    elif evidence in page:
        # exact match, best case
        pass
    else:
        # llms sometimes change a word or two, so do a fuzzy match
        score = fuzz.partial_ratio(evidence, page)
        if score < 90:
            flags.append("evidence not found on page")

    # check 2: is the number actually inside the evidence?
    # this is what catches the "llm said 520 but the paper says 490" case
    if value == "":
        flags.append("no value")
    elif value not in evidence:
        flags.append("value not in evidence")

    # check 3: missing info
    if clean_text(row.get("unit", "")) == "":
        flags.append("missing unit")
    if clean_text(row.get("material", "")) == "":
        flags.append("missing material")
    if clean_text(row.get("conditions", "")) == "":
        flags.append("conditions missing")

    # decide the final status
    if len(flags) == 0:
        status = "verified"
    elif flags == ["conditions missing"]:
        # conditions missing alone is a warning, not a failure
        status = "verified (no conditions)"
    else:
        status = "FLAGGED"

    return status, flags


# ---------------------------------------------------------
# the app itself
# ---------------------------------------------------------
st.title("Datum")
st.write("Turn materials papers into a dataset where every number traces back to its source.")

target_properties = st.text_input(
    "Which properties are you looking for?",
    value="μC*, volumetric capacitance C*, electrical conductivity",
)

uploaded_files = st.file_uploader(
    "Upload papers (PDF)",
    type=["pdf"],
    accept_multiple_files=True,
)

run_button = st.button("Extract")

if run_button:
    api_key = get_api_key()

    if api_key is None or api_key == "":
        st.error("No GEMINI_API_KEY found. Set it as an environment variable or in Streamlit secrets.")
    elif not uploaded_files:
        st.warning("Upload at least one PDF first.")
    else:
        client = genai.Client(api_key=api_key)
        all_rows = []

        for uploaded_file in uploaded_files:
            st.write("Reading: " + uploaded_file.name)
            pages = read_pdf_pages(uploaded_file)

            progress = st.progress(0)
            page_count = len(pages)

            for i in range(page_count):
                page_info = pages[i]
                page_text = page_info["text"]

                # skip basically empty pages, saves api calls
                if len(page_text.strip()) < 50:
                    progress.progress((i + 1) / page_count)
                    continue

                rows = extract_from_page(client, page_text, target_properties)

                for row in rows:
                    status, flags = verify_row(row, page_text)

                    # build the final table row key by key
                    final_row = {}
                    final_row["material"] = row.get("material", "")
                    final_row["property"] = row.get("property", "")
                    final_row["value"] = row.get("value", "")
                    final_row["error"] = row.get("error", "")
                    final_row["unit"] = row.get("unit", "")
                    final_row["conditions"] = row.get("conditions", "")
                    final_row["source_file"] = uploaded_file.name
                    final_row["page"] = page_info["page"]
                    final_row["evidence"] = row.get("evidence", "")
                    final_row["status"] = status
                    final_row["flags"] = ", ".join(flags)

                    all_rows.append(final_row)

                progress.progress((i + 1) / page_count)

        if len(all_rows) == 0:
            st.info("No target properties found in these papers.")
        else:
            table = pd.DataFrame(all_rows)

            # quick summary for the demo
            verified_count = 0
            flagged_count = 0
            for status in table["status"]:
                if status == "FLAGGED":
                    flagged_count = flagged_count + 1
                else:
                    verified_count = verified_count + 1

            st.success(
                "Extracted " + str(len(table)) + " measurements: "
                + str(verified_count) + " verified, "
                + str(flagged_count) + " flagged."
            )

            st.dataframe(table)

            csv_data = table.to_csv(index=False)
            st.download_button(
                "Download CSV",
                data=csv_data,
                file_name="datum_dataset.csv",
                mime="text/csv",
            )