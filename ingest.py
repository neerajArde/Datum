# ingest.py
# stage 1 + 2: pdf -> pages -> only the useful pages -> chunks for the llm
#
# why chunks? sending a whole paper in one llm call is fast, but a page full of
# tables can produce a LOT of output and get cut off. so we group a few pages
# per call: few calls (fast) but small enough answers (safe).

import hashlib

import pymupdf  # reads pdfs page by page (old name: fitz)

from text_tools import normalize

# filler words we never use for the "is this page relevant" check
STOP_WORDS = ["of", "and", "the", "a", "an", "in", "for", "to", "or", "with", "on", "at"]

# limits for one chunk (one llm call)
MAX_PAGES_PER_CHUNK = 4
# kept well under free-tier "tokens per minute" limits (about 4 characters per token)
MAX_CHARS_PER_CHUNK = 9000

# when sending excerpts, keep this many characters on each side of a target word.
# big enough to include a whole table (its header names the property, its rows hold the values)
EXCERPT_RADIUS = 1500

# pages with less text than this are probably blank or just a figure
MIN_PAGE_CHARS = 50


def fingerprint(pdf_bytes):
    # a short id based on the file's CONTENT, not its name.
    # same paper uploaded twice (even renamed) = same id = we can reuse old results
    return hashlib.sha256(pdf_bytes).hexdigest()[:16]


def read_pages(pdf_bytes):
    # open the pdf from memory and grab the text of every page
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

    pages = []
    page_number = 1
    for page in doc:
        page_info = {}
        page_info["page"] = page_number
        page_info["text"] = page.get_text()
        pages.append(page_info)
        page_number = page_number + 1

    doc.close()
    return pages


def property_words(target_properties):
    # "μC*, volumetric capacitance C*" -> ["μc*", "volumetric", "capacitance", "c*"]
    text = normalize(target_properties)
    for separator in [",", ";", "\n"]:
        text = text.replace(separator, " ")

    words = []
    for word in text.split():
        if len(word) < 2:
            continue
        if word in STOP_WORDS:
            continue
        if word not in words:
            words.append(word)
    return words


def is_relevant(page_text, words):
    # cheap check BEFORE we pay for an llm call:
    # does this page mention any of the target property words at all?
    page = normalize(page_text)
    for word in words:
        if word in page:
            return True
    return False


def excerpt(page_text, words):
    # instead of the whole page, keep only the text around the target words.
    # less text = fewer tokens = faster calls and fewer rate limits, and less noise for the ai.
    # verification still checks against the FULL page, so nothing is lost there.
    search_text = page_text.lower().replace("\u00b5", "\u03bc")   # µ (micro) -> μ (mu), same length
    windows = []
    for word in words:
        start = search_text.find(word)
        while start != -1:
            windows.append([max(0, start - EXCERPT_RADIUS), min(len(page_text), start + len(word) + EXCERPT_RADIUS)])
            start = search_text.find(word, start + 1)

    if len(windows) == 0:
        return page_text

    # merge windows that overlap
    windows.sort()
    merged = [windows[0]]
    for window in windows[1:]:
        last = merged[-1]
        if window[0] <= last[1]:
            last[1] = max(last[1], window[1])
        else:
            merged.append(window)

    kept = sum(window[1] - window[0] for window in merged)
    if kept > 0.8 * len(page_text):
        return page_text   # almost the whole page anyway

    pieces = []
    for window in merged:
        pieces.append(page_text[window[0]:window[1]])
    return "\n[...]\n".join(pieces)


def chunk_from_blocks(blocks):
    # a chunk = a few pages glued together, each starting with a page marker
    # so the llm can tell us which page a value came from
    chunk = {}
    chunk["pages"] = []
    chunk["blocks"] = blocks
    text = ""
    for block in blocks:
        chunk["pages"].append(block["page"])
        text = text + block["text"]
    chunk["text"] = text
    return chunk


def split_chunk(chunk):
    # cut a chunk in half (used when the llm answer got cut off)
    middle = len(chunk["blocks"]) // 2
    left = chunk_from_blocks(chunk["blocks"][:middle])
    right = chunk_from_blocks(chunk["blocks"][middle:])
    return left, right


def make_chunks(pages, words, filter_pages):
    # returns (chunks, number of pages we kept)
    chunks = []
    current_blocks = []
    current_chars = 0
    pages_kept = 0

    for page_info in pages:
        text = page_info["text"]

        # skip blank / figure-only pages
        if len(text.strip()) < MIN_PAGE_CHARS:
            continue

        # skip pages that never mention a target property (references, acknowledgements...)
        if filter_pages and not is_relevant(text, words):
            continue

        block = {}
        block["page"] = page_info["page"]
        page_text = text
        if filter_pages:
            page_text = excerpt(text, words)
        block["text"] = "=== PAGE " + str(page_info["page"]) + " ===\n" + page_text + "\n"

        # start a new chunk if this page would make the current one too big
        too_many_pages = len(current_blocks) >= MAX_PAGES_PER_CHUNK
        too_many_chars = current_chars + len(block["text"]) > MAX_CHARS_PER_CHUNK
        if len(current_blocks) > 0 and (too_many_pages or too_many_chars):
            chunks.append(chunk_from_blocks(current_blocks))
            current_blocks = []
            current_chars = 0

        current_blocks.append(block)
        current_chars = current_chars + len(block["text"])
        pages_kept = pages_kept + 1

    if len(current_blocks) > 0:
        chunks.append(chunk_from_blocks(current_blocks))

    return chunks, pages_kept
