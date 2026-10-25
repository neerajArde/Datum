# ui.py
# the look of datum. all styling and small html pieces live here, so app.py stays readable.
#
# design idea: a lab-bench instrument, not a dashboard.
# the ONE bold thing is highlighter yellow, used only where datum shows proof
# (the quoted evidence and the highlighted pdf page). everything else stays quiet.
# app text is a sans-serif; words quoted from papers are a serif, so "the paper's words"
# always look different from "the app's words".

import html

from schema import STATUS_FLAGGED, STATUS_REVIEW, STATUS_VERIFIED

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&family=Schibsted+Grotesk:wght@400;500;600;700;800&display=swap');

:root {
  --bench: #ECEEF1;
  --surface: #FFFFFF;
  --ink: #121A23;
  --panel: #172230;
  --panel-line: #2A3747;
  --muted: #5C6773;
  --line: #CDD3DA;
  --action: #121A23;
  --highlight: #FFE14D;
  --verified: #3FA66B;
  --review: #D19A2E;
  --flagged: #D2514C;
  --prism-red: rgba(227, 123, 143, .25);
  --prism-blue: rgba(100, 156, 237, .30);
}

/* every piece of app text, but never streamlit's icon font (icons are words in that font) */
.stApp *:not([data-testid="stIconMaterial"]):not(.material-symbols-rounded):not(code):not(pre) {
  font-family: 'Schibsted Grotesk', system-ui, sans-serif;
}
.stApp .dt-quote, .stApp .dt-quote * { font-family: 'Newsreader', Georgia, serif !important; }

/* the header: a wordmark and one plain sentence */
.dt-hero { position: relative; overflow: hidden; isolation: isolate; padding: 1.6rem 1.6rem 1.4rem; margin-bottom: 1.5rem;
  border-radius: 16px; border: 1px solid rgba(255,255,255,.8);
  background: radial-gradient(ellipse at 50% 120%, #CCD5E2, transparent 65%), linear-gradient(145deg, #EDF0F4, #E1E5ED 55%, #E9EAF0);
  box-shadow: inset 0 1px 0 white, 0 18px 40px rgba(18,26,35,.06); }
.dt-ghost { position: absolute; right: -0.05em; bottom: -0.28em; z-index: -1; font-size: 9rem; font-weight: 800; letter-spacing: -0.06em;
  color: #fff; filter: blur(12px); opacity: .9; text-shadow: 0 0 30px white; pointer-events: none; user-select: none; }
.dt-mark { font-size: 2.6rem; font-weight: 800; letter-spacing: -0.04em; line-height: 1; color: var(--ink); }
.dt-mark .dot { display: inline-block; width: 0.42em; height: 0.42em; background: var(--highlight);
  border-radius: 2px; margin-left: 0.08em; transform: translateY(-0.05em); }
.dt-lede { font-size: 1.05rem; color: var(--muted); max-width: 44rem; margin: 0.6rem 0 0 0; line-height: 1.5; }

/* the trust bar: how much of the table is backed by the paper */
.dt-trust { background: var(--panel); color: #DCE3EA; border-radius: 14px; padding: 1.2rem 1.4rem; margin: 0.5rem 0 1rem 0;
  box-shadow: inset 0 1px 0 rgba(255,255,255,.08), 0 18px 40px rgba(18,26,35,.10); }
.dt-trust-head { display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 0.5rem;
  padding-bottom: .8rem; border-bottom: 1px solid var(--panel-line); }
.stApp .dt-trust-title { font-size: 1.15rem; font-weight: 600; color: #fff; }
.stApp .dt-trust-meta { font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem; color: #8C99A8; }
.dt-bar { display: flex; height: 10px; border-radius: 5px; overflow: hidden; background: rgba(255,255,255,.06); margin: 1rem 0 0.8rem 0; }
.dt-bar span { display: block; height: 100%; }
.dt-bar .v { background: var(--verified); }
.dt-bar .r { background: repeating-linear-gradient(125deg, transparent 0 4px, rgba(255,255,255,.22) 4px 5px), var(--review); }
.dt-bar .f { background: var(--flagged); }
.dt-legend { display: flex; gap: 1.5rem; flex-wrap: wrap; font-size: 0.9rem; color: #A9B4C0; }
.dt-legend b { font-size: 1.15rem; color: #fff; margin-right: 0.3rem; }
.dt-swatch { display: inline-block; width: 0.6rem; height: 0.6rem; border-radius: 2px; margin-right: 0.4rem; }

/* the evidence card: the moment datum proves a number */
.dt-card { border-radius: 16px; padding: 1.3rem 1.5rem; border: 1px solid rgba(255,255,255,.85);
  background: linear-gradient(130deg, rgba(255,255,255,.85), rgba(255,255,255,.55));
  backdrop-filter: blur(20px) saturate(1.4); -webkit-backdrop-filter: blur(20px) saturate(1.4);
  box-shadow: inset 0 1px 0 white, -1px 0 0 var(--prism-red), 1px 0 0 var(--prism-blue), 0 20px 50px rgba(43,57,83,.12); }
.dt-card-sub { font-size: 0.9rem; color: var(--muted); margin-bottom: 0.2rem; }
.dt-card-value { font-size: 2.1rem; font-weight: 600; color: var(--ink); letter-spacing: -0.01em; line-height: 1.15; }
.dt-card-value .unit { font-size: 1.05rem; font-weight: 500; color: var(--muted); margin-left: 0.35rem; }
.dt-pill { display: inline-block; font-size: 0.82rem; font-weight: 600; padding: 0.15rem 0.6rem; border-radius: 999px; margin: 0.6rem 0 0.9rem 0; }
.dt-pill.verified { background: #E3F2E9; color: var(--verified); }
.dt-pill.review { background: #FBF0DC; color: var(--review); }
.dt-pill.flagged { background: #F8E1E1; color: var(--flagged); }
.dt-quote { font-family: 'Newsreader', Georgia, serif; font-size: 1.12rem; line-height: 1.6; color: var(--ink);
  border-left: 3px solid var(--highlight); padding: 0.1rem 0 0.1rem 0.9rem; margin: 0.25rem 0 0.4rem 0; }
.dt-quote mark { background: var(--highlight); color: var(--ink); padding: 0 0.12em; border-radius: 2px; }
.dt-source { font-size: 0.85rem; color: var(--muted); margin-bottom: 0.9rem; }
.dt-checks { margin: 0; padding-left: 1.1rem; color: var(--muted); font-size: 0.9rem; line-height: 1.55; }


/* ---------- threads layout ---------- */
/* hide streamlit's own top bar: the page is the product */
[data-testid="stToolbar"], [data-testid="stDecoration"] { display: none !important; }
header[data-testid="stHeader"] { background: transparent !important; }
.block-container { max-width: 1100px; padding-top: 2.2rem !important; padding-bottom: 7rem !important; }

/* sidebar: a quiet list, like a chat app */
[data-testid="stSidebar"] { background: linear-gradient(180deg, #F4F5F8, #E7EAF0) !important; border-right: 1px solid var(--line); }
.dt-side-mark { font-size: 1.35rem; font-weight: 800; letter-spacing: -0.03em; color: var(--ink); margin: 0.2rem 0 1rem 0.2rem; }
.dt-side-mark .dot { display: inline-block; width: 0.42em; height: 0.42em; background: var(--highlight); border-radius: 2px; margin-left: 0.08em; }
[data-testid="stSidebar"] .stButton button { justify-content: flex-start !important; text-align: left; font-weight: 500;
  border-radius: 10px !important; padding: 0.45rem 0.7rem !important; min-height: 0 !important; }
[data-testid="stSidebar"] .stButton button p { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 0.92rem; }
[data-testid="stSidebar"] .stButton button[kind="secondary"] { background: transparent !important; border: 1px solid transparent !important; box-shadow: none !important; color: var(--muted) !important; }
[data-testid="stSidebar"] .stButton button[kind="secondary"]:hover { background: rgba(255,255,255,.6) !important; color: var(--ink) !important; }
[data-testid="stSidebar"] .stButton button[kind="primary"] { background: rgba(255,255,255,.92) !important; color: var(--ink) !important;
  border: 1px solid rgba(255,255,255,.95) !important; box-shadow: inset 0 1px 0 white, 0 4px 14px rgba(18,26,35,.07) !important; }
[data-testid="stSidebar"] .st-key-new_thread button[kind], [data-testid="stSidebar"] .st-key-new_thread button[kind]:hover { background: var(--ink) !important; color: #fff !important; border: 0 !important;
  margin-bottom: 0.9rem; justify-content: center !important; box-shadow: inset 0 1px 0 rgba(255,255,255,.18), 0 6px 18px rgba(18,26,35,.18) !important; }
[data-testid="stSidebar"] .st-key-new_thread button p, [data-testid="stSidebar"] .st-key-new_thread button span { color: #fff !important; }
.dt-sidebar-spacer { height: 1.2rem; }

/* empty thread: one line, nothing else */
.dt-empty { position: relative; isolation: isolate; text-align: center; padding: 18vh 1rem 0 1rem; }
.dt-empty-ghost { position: absolute; left: 50%; top: 9vh; transform: translateX(-50%); z-index: -1; font-size: clamp(7rem, 20vw, 15rem);
  font-weight: 800; letter-spacing: -0.06em; color: #fff; filter: blur(16px); opacity: .95; text-shadow: 0 0 40px white; pointer-events: none; user-select: none; white-space: nowrap; }
.stApp .dt-empty h1 { font-size: clamp(2rem, 4vw, 3rem); letter-spacing: -0.04em; line-height: 1.05; font-weight: 700; margin: 0; color: var(--ink); }
.stApp .dt-empty p { color: var(--muted); margin: 0.9rem auto 0; max-width: 30rem; font-size: 1rem; }

/* what the researcher asked for, shown like a sent message */
.dt-ask { display: flex; justify-content: flex-end; margin: 1.6rem 0 0.8rem 0; }
.dt-ask-inner { max-width: 70%; background: var(--ink); color: #fff; border-radius: 18px 18px 4px 18px; padding: 0.75rem 1rem;
  box-shadow: 0 10px 24px rgba(18,26,35,.12); }
.stApp .dt-ask-props { font-weight: 600; font-size: 0.98rem; color: #fff; }
.dt-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 0.45rem; }
.stApp .dt-chip { font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem; color: #C9D2DC; background: rgba(255,255,255,.08);
  border: 1px solid rgba(255,255,255,.12); border-radius: 6px; padding: 2px 7px; }

/* the input bar: frosted glass with the prism edge */
[data-testid="stChatInput"] { border-radius: 20px !important; border: 1px solid rgba(255,255,255,.9) !important;
  background: linear-gradient(130deg, rgba(255,255,255,.92), rgba(255,255,255,.7)) !important;
  backdrop-filter: blur(20px) saturate(1.4); -webkit-backdrop-filter: blur(20px) saturate(1.4);
  box-shadow: inset 0 1px 0 white, -1px 0 0 var(--prism-red), 1px 0 0 var(--prism-blue), 0 18px 44px rgba(43,57,83,.14) !important; }
[data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] { background: transparent !important; }
[data-testid="stChatInput"] textarea, [data-testid="stChatInput"] textarea:focus, [data-testid="stChatInput"] textarea:focus-visible { outline: none !important; box-shadow: none !important; border: 0 !important; }
[data-testid="stChatInput"]:focus-within { border-color: rgba(18,26,35,.28) !important; }
[data-testid="stBottom"] { background: linear-gradient(180deg, rgba(236,238,241,0), var(--bench) 45%) !important; }

/* quieter streamlit defaults */
[data-testid="stSidebar"] { border-right: 1px solid var(--line); }
.stButton button, .stDownloadButton button { border-radius: 999px !important; font-weight: 600; position: relative; overflow: hidden;
  box-shadow: inset 0 1px 0 rgba(255,255,255,.8), -1px 0 0 var(--prism-red), 1px 0 0 var(--prism-blue), 0 8px 24px rgba(18,26,35,.08); }
.stButton button[kind="primary"], .stDownloadButton button[kind="primary"] {
  background: linear-gradient(160deg, rgba(44,56,72,.96), rgba(18,26,35,.98)) !important; border-color: rgba(255,255,255,.35) !important; color: #fff !important; }
.stButton button::after, .stDownloadButton button::after { content: ''; pointer-events: none; position: absolute; top: -60%; bottom: -60%; left: -80%;
  width: 40%; transform: skewX(-22deg); background: linear-gradient(90deg, transparent, rgba(255,255,255,.35), transparent); }
@media (hover: hover) { .stButton button:hover::after, .stDownloadButton button:hover::after { animation: dt-sheen .8s ease both; } }
@keyframes dt-sheen { to { left: 150%; } }
[data-testid="stFileUploaderDropzone"], [data-testid="stExpander"] details { border-radius: 14px !important; border: 1px solid var(--line) !important;
  background: rgba(255,255,255,.6) !important; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #F4F5F8, #E9ECF1) !important; }
@media (prefers-reduced-motion: reduce) { .stButton button::after, .stDownloadButton button::after { animation: none !important; } }
:focus-visible { outline: 2px solid var(--action) !important; outline-offset: 2px; }
@media (max-width: 640px) { .dt-mark { font-size: 2.4rem; } .dt-card-value { font-size: 1.7rem; } }
</style>
"""

STATUS_WORDS = {
    STATUS_VERIFIED: "Verified",
    STATUS_REVIEW: "Needs review",
    STATUS_FLAGGED: "Flagged",
}


def hero():
    # same idea as the landing page: a frosted giant wordmark behind a short plain line
    text = ""
    text = text + '<div class="dt-hero">'
    text = text + '<div class="dt-ghost" aria-hidden="true">Datum</div>'
    text = text + '<div class="dt-mark">Datum<span class="dot"></span></div>'
    text = text + '<p class="dt-lede">Pull measurements out of research papers into one table. '
    text = text + "Every number is checked against the page it came from, and anything doubtful is marked.</p>"
    text = text + "</div>"
    return text


def trust_bar(rows, stats):
    counts = {STATUS_VERIFIED: 0, STATUS_REVIEW: 0, STATUS_FLAGGED: 0}
    for row in rows:
        counts[row["status"]] = counts[row["status"]] + 1
    total = len(rows)

    papers = stats["papers"]
    meta = str(papers) + (" paper" if papers == 1 else " papers")
    meta = meta + ", " + str(stats["pages_sent"]) + " of " + str(stats["pages_total"]) + " pages read"
    meta = meta + ", " + str(stats["seconds"]) + " s"
    if stats["papers_from_cache"] > 0:
        meta = meta + " (" + str(stats["papers_from_cache"]) + " reused from earlier runs)"

    text = ""
    text = text + '<div class="dt-trust">'
    text = text + '<div class="dt-trust-head">'
    text = text + '<div class="dt-trust-title">' + str(total) + " measurements found</div>"
    text = text + '<div class="dt-trust-meta">' + html.escape(meta) + "</div>"
    text = text + "</div>"
    text = text + '<div class="dt-bar" role="img" aria-label="' + str(counts[STATUS_VERIFIED]) + " verified, "
    text = text + str(counts[STATUS_REVIEW]) + " need review, " + str(counts[STATUS_FLAGGED]) + ' flagged">'
    text = text + '<span class="v" style="flex:' + str(counts[STATUS_VERIFIED]) + '"></span>'
    text = text + '<span class="r" style="flex:' + str(counts[STATUS_REVIEW]) + '"></span>'
    text = text + '<span class="f" style="flex:' + str(counts[STATUS_FLAGGED]) + '"></span>'
    text = text + "</div>"
    text = text + '<div class="dt-legend">'
    text = text + legend_item(counts[STATUS_VERIFIED], "verified: value found on its page", "var(--verified)")
    text = text + legend_item(counts[STATUS_REVIEW], "need a quick look", "var(--review)")
    text = text + legend_item(counts[STATUS_FLAGGED], "flagged: not backed by the paper", "var(--flagged)")
    text = text + "</div></div>"
    return text


def legend_item(count, words, color):
    text = "<span>"
    text = text + '<span class="dt-swatch" style="background:' + color + '"></span>'
    text = text + "<b>" + str(count) + "</b>" + html.escape(words)
    text = text + "</span>"
    return text


def quote_with_mark(evidence, value):
    # escape the quote first (it comes from a pdf), then highlight the value inside it
    safe = html.escape(" ".join(str(evidence).split()))
    value = str(value).strip()
    if value != "":
        safe_value = html.escape(value)
        position = safe.find(safe_value)
        if position != -1:
            safe = safe[:position] + "<mark>" + safe_value + "</mark>" + safe[position + len(safe_value):]
    return safe


def evidence_card(row):
    value_text = html.escape(str(row["value"]))
    if row["error"]:
        value_text = value_text + " ± " + html.escape(str(row["error"]))

    property_name = row["property_std"] if row.get("property_std") else row["property"]
    source = "Page " + str(row["page"]) + " of " + str(row["paper"])
    if row.get("reference"):
        source = source + ", originally from reference [" + str(row["reference"]) + "]"

    text = ""
    text = text + '<div class="dt-card">'
    text = text + '<div class="dt-card-sub">' + html.escape(str(row["material"])) + ", " + html.escape(str(property_name)) + "</div>"
    text = text + '<div class="dt-card-value">' + value_text
    text = text + '<span class="unit">' + html.escape(str(row["unit"])) + "</span></div>"
    if row["value_std"] and row["unit_std"] and row["unit_std"] != row["unit"]:
        text = text + '<div class="dt-card-sub">= ' + html.escape(str(row["value_std"])) + " " + html.escape(str(row["unit_std"])) + "</div>"
    text = text + '<span class="dt-pill ' + row["status"] + '">' + STATUS_WORDS[row["status"]] + "</span>"
    text = text + '<div class="dt-quote">' + quote_with_mark(row["evidence"], row["value"]) + "</div>"
    text = text + '<div class="dt-source">' + html.escape(source) + "</div>"
    if row["conditions"]:
        text = text + '<div class="dt-source">Conditions: ' + html.escape(str(row["conditions"])) + "</div>"
    if row["checks"]:
        text = text + '<ul class="dt-checks">'
        for check in str(row["checks"]).split("; "):
            text = text + "<li>" + html.escape(check) + "</li>"
        text = text + "</ul>"
    text = text + "</div>"
    return text


def sidebar_mark():
    return '<div class="dt-side-mark">Datum<span class="dot"></span></div>'


def empty_state():
    text = ""
    text = text + '<div class="dt-empty">'
    text = text + '<div class="dt-empty-ghost" aria-hidden="true">Datum</div>'
    text = text + "<h1>Drop papers. Name the properties.</h1>"
    text = text + "<p>Attach PDFs with the paperclip below and type what to pull out. "
    text = text + "You get one table, every value checked against its page.</p>"
    text = text + "</div>"
    return text


def request_bubble(properties, paper_names):
    text = ""
    text = text + '<div class="dt-ask"><div class="dt-ask-inner">'
    text = text + '<div class="dt-ask-props">' + html.escape(str(properties)) + "</div>"
    text = text + '<div class="dt-chips">'
    for name in paper_names:
        text = text + '<span class="dt-chip">' + html.escape(str(name)) + "</span>"
    text = text + "</div></div></div>"
    return text


def run_summary(result):
    # one line for a folded-away earlier run
    counts = {STATUS_VERIFIED: 0, STATUS_REVIEW: 0, STATUS_FLAGGED: 0}
    for row in result["rows"]:
        counts[row["status"]] = counts[row["status"]] + 1
    text = str(len(result["rows"])) + " values · "
    text = text + str(counts[STATUS_VERIFIED]) + " verified · "
    text = text + str(counts[STATUS_REVIEW]) + " to review · "
    text = text + str(counts[STATUS_FLAGGED]) + " flagged"
    return text
