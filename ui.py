# ui.py
# the look of datum. all styling and small html pieces live here, so app.py stays readable.
#
# direction: a calm workspace for researchers who use it every day.
# neutral background, fine borders, small type, very little text.
# the ONE expressive element is the liquid-glass capsule that slides along the pipeline
# while papers are processed. yellow is only ever used for evidence (highlighted values).

import html

from schema import STATUS_FLAGGED, STATUS_REVIEW, STATUS_VERIFIED

STAGE_LABELS = ["Ingest", "Filter", "Extract", "Verify", "Assemble"]

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&family=Schibsted+Grotesk:wght@400;500;600;700;800&display=swap');

:root {
  --bench: #F2F3F5;
  --surface: #FFFFFF;
  --sunk: #F7F8FA;
  --ink: #15191F;
  --muted: #6A7380;
  --faint: #9AA3AE;
  --line: #E1E4E8;
  --line-strong: #CDD2D8;
  --highlight: #FFE14D;
  --verified: #2F9461;
  --review: #C98A1E;
  --flagged: #C9483F;
}

/* every piece of app text, but never streamlit's icon font (icons are words in that font) */
.stApp *:not([data-testid="stIconMaterial"]):not(.material-symbols-rounded):not(code):not(pre) {
  font-family: 'Schibsted Grotesk', system-ui, sans-serif;
}
.stApp .dt-quote, .stApp .dt-quote * { font-family: 'Newsreader', Georgia, serif !important; }

/* streamlit chrome off: the page is the product */
[data-testid="stToolbar"], [data-testid="stDecoration"] { display: none !important; }
header[data-testid="stHeader"] { background: transparent !important; }
.block-container { max-width: 1040px; padding-top: 2rem !important; padding-bottom: 4rem !important; }
:focus-visible { outline: 2px solid var(--ink) !important; outline-offset: 2px; }

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] { background: var(--sunk) !important; border-right: 1px solid var(--line); }
.dt-side-mark { font-size: 1.15rem; font-weight: 800; letter-spacing: -0.03em; color: var(--ink); margin: 0 0 .9rem .35rem; }
.dt-side-mark .dot { display: inline-block; width: .42em; height: .42em; background: var(--highlight); border-radius: 2px; margin-left: .08em; }
.dt-side-mark a { color: inherit !important; text-decoration: none !important; }
.stApp .dt-side-note { font-size: .74rem; line-height: 1.4; color: var(--faint); margin: 1.2rem .4rem .2rem; }
.stApp .dt-side-link { margin: .5rem .4rem 0; font-size: .8rem; }
.stApp .dt-side-link a { color: var(--muted, #5A636E) !important; text-decoration: none !important; }
.stApp .dt-side-link a:hover { color: var(--ink) !important; }
.stApp [class*="st-key-pick_"] button { background: var(--surface) !important; border: 1px solid var(--line) !important; color: #3A424C !important; }
.stApp [class*="st-key-pick_"] button:hover { border-color: #C3C9D0 !important; }
.stApp [class*="st-key-pick_"] button[aria-pressed="true"], .stApp [class*="st-key-pick_"] button[aria-checked="true"] { background: var(--ink) !important; border-color: var(--ink) !important; color: #fff !important; }
.stApp [class*="st-key-pick_"] button[aria-pressed="true"] p, .stApp [class*="st-key-pick_"] button[aria-checked="true"] p { color: #fff !important; }
.stApp .dt-side-label { font-size: .74rem; color: var(--faint); margin: 1.1rem 0 .3rem .4rem; }
[data-testid="stSidebar"] .stButton button { justify-content: flex-start !important; text-align: left; font-weight: 500; font-size: .9rem;
  border-radius: 8px !important; padding: .38rem .6rem !important; min-height: 0 !important; box-shadow: none !important; }
[data-testid="stSidebar"] .stButton button > div { justify-content: flex-start !important; width: 100%; }
[data-testid="stSidebar"] .stButton button p { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: .9rem; }
[data-testid="stSidebar"] .stButton button[kind="secondary"] { background: transparent !important; border: 1px solid transparent !important; color: #3A424C !important; }
[data-testid="stSidebar"] .stButton button[kind="secondary"]:hover { background: #ECEEF1 !important; }
[data-testid="stSidebar"] .stButton button[kind="primary"] { background: var(--surface) !important; color: var(--ink) !important; border: 1px solid var(--line) !important; }
[data-testid="stSidebar"] .st-key-new_thread button[kind], [data-testid="stSidebar"] .st-key-new_thread button[kind]:hover {
  background: var(--surface) !important; border: 1px solid var(--line-strong) !important; color: var(--ink) !important; }
[data-testid="stSidebar"] [data-testid="stPopover"] button { border: 0 !important; background: transparent !important; box-shadow: none !important;
  padding: .38rem .3rem !important; min-height: 0 !important; color: var(--faint) !important; }
[data-testid="stSidebar"] [data-testid="stPopover"] button:hover { color: var(--ink) !important; background: #ECEEF1 !important; }
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] { gap: .15rem !important; align-items: center; }

/* ---------- thread header ---------- */
.dt-title { display: flex; align-items: baseline; gap: .7rem; margin: 0 0 1.1rem 0; }
.stApp .dt-title .name { font-size: 1.3rem; font-weight: 600; letter-spacing: -.02em; color: var(--ink); }
.stApp .dt-title .count { font-size: .85rem; color: var(--faint); }

/* ---------- the composer: properties, papers, extract ---------- */
.st-key-composer { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 1rem 1.1rem 1.05rem !important; }
.st-key-composer [data-testid="stTextInput"] > div > div { border-radius: 8px !important; background: var(--sunk) !important; border: 1px solid var(--line) !important; }
.st-key-composer label p { font-size: .8rem !important; color: var(--muted) !important; font-weight: 500 !important; }
.stApp .dt-files-label { font-size: .8rem; color: var(--muted); font-weight: 500; margin: .2rem 0 .35rem 0; }
.st-key-composer [data-testid="stFileUploaderDropzone"] { border: 1px dashed var(--line-strong) !important; background: var(--sunk) !important;
  border-radius: 8px !important; padding: .55rem .8rem !important; }
.st-key-composer [data-testid="stFileUploaderDropzoneInstructions"] small { display: none !important; }
.st-key-composer [data-testid="stFileUploaderFile"], .st-key-composer [data-testid="stFileUploaderPagination"] { display: none !important; }
.st-key-composer .stButton button[kind="primary"] { padding: .45rem 1.1rem !important; }

/* uploaded pdfs: compact file items with a remove action */
[class*="st-key-paper_"] { background: var(--sunk); border: 1px solid var(--line); border-radius: 8px; padding: .3rem .3rem .3rem .7rem !important; }
[class*="st-key-paper_"] [data-testid="stMarkdownContainer"] { margin: 0 !important; }
[class*="st-key-paper_"] [data-testid="stElementContainer"] { margin: 0 !important; }
[class*="st-key-paper_"] [data-testid="stHorizontalBlock"] { align-items: center; gap: .3rem !important; }
.stApp .dt-file { font-size: .86rem; line-height: 1.6; color: var(--ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.stApp .dt-file small { color: var(--faint); margin-left: .45rem; font-size: .76rem; }
[class*="st-key-paper_"] .stButton button { border: 0 !important; background: transparent !important; box-shadow: none !important; min-height: 0 !important;
  padding: .1rem .35rem !important; color: var(--faint) !important; }
[class*="st-key-paper_"] .stButton button:hover { color: var(--flagged) !important; }

/* ---------- the pipeline, with the sliding liquid-glass capsule ---------- */
.dt-pipe { margin: 1.3rem 0 .4rem 0; }
.dt-pipe-track { position: relative; display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); padding: 5px;
  background: var(--sunk); border: 1px solid var(--line); border-radius: 14px; isolation: isolate; overflow: hidden; }
.stApp .dt-pipe-stage { position: relative; z-index: 2; text-align: center; padding: .62rem .3rem; font-size: .9rem; font-weight: 500; color: var(--faint);
  white-space: nowrap; transition: color .4s ease; }
.dt-pipe-stage .mark { display: inline-block; width: 1.05em; margin-right: .2em; font-size: .85em; }
.stApp .dt-pipe-stage.done { color: var(--muted); }
.stApp .dt-pipe-stage.done .mark { color: var(--verified); }
.stApp .dt-pipe-stage.active { color: var(--ink); font-weight: 600; }
.stApp .dt-pipe-stage.failed { color: var(--flagged); font-weight: 600; }

/* the capsule: frosted surface, bright thin edge, soft inner shadow, faint refracted glow.
   it is re-drawn on every REAL progress event and animates from the previous stage (--from)
   to the current one (--to), so it only slides when the backend actually moves on */
.dt-glass { position: absolute; z-index: 1; top: 5px; bottom: 5px; left: 5px; width: calc((100% - 10px) / 5); border-radius: 10px;
  background: linear-gradient(180deg, rgba(255,255,255,.95), rgba(255,255,255,.6));
  backdrop-filter: blur(14px) saturate(1.6); -webkit-backdrop-filter: blur(14px) saturate(1.6);
  border: 1px solid rgba(255,255,255,.95);
  box-shadow: inset 0 1px 0 #fff, inset 0 -6px 12px rgba(21,25,31,.05), 0 6px 18px rgba(21,25,31,.09),
              -1px 0 0 rgba(227,123,143,.30), 1px 0 0 rgba(100,156,237,.34), 0 0 22px rgba(160,190,255,.22);
  transform: translateX(calc(var(--to) * 100%));
  animation: dt-slide .7s cubic-bezier(.22,.9,.26,1) both; overflow: hidden; }
@keyframes dt-slide { from { transform: translateX(calc(var(--from) * 100%)); } to { transform: translateX(calc(var(--to) * 100%)); } }
/* gentle light shimmer while the stage is working */
.dt-glass.working::after { content: ""; position: absolute; top: 0; bottom: 0; left: -60%; width: 50%;
  background: linear-gradient(100deg, transparent, rgba(255,255,255,.8), rgba(200,220,255,.4), transparent);
  animation: dt-shimmer 1.8s ease-in-out infinite; }
@keyframes dt-shimmer { to { left: 120%; } }
.dt-glass.failed { background: linear-gradient(180deg, rgba(255,242,240,.96), rgba(255,228,224,.75)); box-shadow: inset 0 1px 0 #fff, 0 6px 18px rgba(201,72,63,.16); }
.dt-glass.hidden { display: none; }
.stApp .dt-pipe-status { font-size: .86rem; color: var(--muted); margin: .55rem .2rem 0 .2rem; min-height: 1.3em; }
.dt-pipe.compact { margin: .2rem 0 1rem 0; }
.dt-pipe.compact .dt-pipe-track { padding: 3px; border-radius: 10px; }
.stApp .dt-pipe.compact .dt-pipe-stage { padding: .28rem .2rem; font-size: .78rem; }

/* ---------- results ---------- */
.dt-summary { display: flex; align-items: center; gap: 1.1rem; flex-wrap: wrap; min-height: 2.4rem; }
.stApp .dt-summary .count { font-size: 1.05rem; font-weight: 600; color: var(--ink); }
.dt-thinbar { display: flex; flex: 1 1 120px; max-width: 220px; height: 6px; border-radius: 3px; overflow: hidden; background: var(--line); }
.dt-thinbar span { display: block; height: 100%; }
.dt-thinbar .v { background: var(--verified); } .dt-thinbar .r { background: var(--review); } .dt-thinbar .f { background: var(--flagged); }
.stApp .dt-legend { font-size: .84rem; color: var(--muted); display: flex; gap: .9rem; flex-wrap: wrap; }
.dt-legend i { display: inline-block; width: .5rem; height: .5rem; border-radius: 50%; margin-right: .35rem; }
.stApp .dt-meta { font-size: .78rem; color: var(--faint); }
[data-testid="stExpander"] details { border: 1px solid var(--line) !important; border-radius: 10px !important; background: var(--surface) !important; }
[data-testid="stExpander"] summary p { font-size: .86rem; color: var(--muted); }
.stButton button, .stDownloadButton button { border-radius: 8px !important; font-weight: 600; }

/* evidence: plain, fine-bordered, the value highlighted in the paper's own words */
.dt-card { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 1.1rem 1.25rem; }
.stApp .dt-card-sub { font-size: .85rem; color: var(--muted); margin-bottom: .15rem; }
.stApp .dt-card-value { font-size: 1.9rem; font-weight: 600; color: var(--ink); letter-spacing: -.01em; line-height: 1.15; }
.stApp .dt-card-value .unit { font-size: 1rem; font-weight: 500; color: var(--muted); margin-left: .35rem; }
.dt-pill { display: inline-block; font-size: .78rem; font-weight: 600; padding: .12rem .55rem; border-radius: 999px; margin: .55rem 0 .8rem 0; }
.dt-pill.verified { background: #E5F3EB; color: var(--verified); }
.dt-pill.review { background: #FBF1DE; color: var(--review); }
.dt-pill.flagged { background: #F8E3E1; color: var(--flagged); }
.stApp .dt-quote { font-size: 1.08rem; line-height: 1.6; color: var(--ink); border-left: 3px solid var(--highlight); padding: .05rem 0 .05rem .85rem; margin: .2rem 0 .4rem 0; }
.dt-quote mark { background: var(--highlight); color: var(--ink); padding: 0 .12em; border-radius: 2px; }
.stApp .dt-source { font-size: .82rem; color: var(--muted); margin-bottom: .7rem; }
.stApp .dt-checks { margin: 0; padding-left: 1.05rem; color: var(--muted); font-size: .85rem; line-height: 1.55; }

@media (max-width: 640px) {
  .stApp .dt-pipe-stage { font-size: .72rem; padding: .55rem .1rem; }
  .dt-pipe-stage .mark { display: none; }
  .stApp .dt-card-value { font-size: 1.5rem; }
}
@media (prefers-reduced-motion: reduce) {
  .dt-glass { animation: none !important; }
  .dt-glass.working::after { animation: none !important; display: none; }
  .stApp .dt-pipe-stage { transition: none !important; }
}
</style>
"""

STATUS_WORDS = {
    STATUS_VERIFIED: "Verified",
    STATUS_REVIEW: "Needs review",
    STATUS_FLAGGED: "Flagged",
}


def sidebar_mark(link=""):
    mark = 'Datum<span class="dot"></span>'
    if link:
        mark = '<a href="' + html.escape(link) + '" target="_blank" rel="noopener" title="About Datum">' + mark + "</a>"
    return '<div class="dt-side-mark">' + mark + "</div>"


def side_note(text):
    return '<div class="dt-side-note">' + html.escape(text) + "</div>"


def side_link(text, link):
    return ('<div class="dt-side-link"><a href="' + html.escape(link) + '" target="_blank" rel="noopener">'
            + html.escape(text) + " ↗</a></div>")


def side_label(text):
    return '<div class="dt-side-label">' + html.escape(text) + "</div>"


def thread_header(title, paper_count):
    text = '<div class="dt-title"><span class="name">' + html.escape(title) + "</span>"
    if paper_count > 0:
        text = text + '<span class="count">' + str(paper_count) + (" paper" if paper_count == 1 else " papers") + "</span>"
    text = text + "</div>"
    return text


def file_item(name, size_bytes):
    if size_bytes >= 1024 * 1024:
        size = str(round(size_bytes / 1024 / 1024, 1)) + " MB"
    else:
        size = str(max(1, round(size_bytes / 1024))) + " KB"
    return '<div class="dt-file">' + html.escape(name) + "<small>" + size + "</small></div>"


def pipeline(states, current, previous, status, compact=False):
    # states: "done" / "active" / "todo" / "failed" for each of the five stages
    # current / previous: where the capsule moves TO and FROM (current None hides it)
    classes = "dt-pipe compact" if compact else "dt-pipe"
    to_index = current if current is not None else 0
    from_index = previous if previous is not None else to_index

    text = '<div class="' + classes + '">'
    text = text + '<div class="dt-pipe-track" style="--from:' + str(from_index) + "; --to:" + str(to_index) + '">'
    glass = "dt-glass"
    if current is None:
        glass = glass + " hidden"
    elif states[current] == "failed":
        glass = glass + " failed"
    elif states[current] == "active":
        glass = glass + " working"
    text = text + '<div class="' + glass + '" aria-hidden="true"></div>'
    for index in range(len(STAGE_LABELS)):
        state = states[index]
        mark = ""
        if state == "done":
            mark = "✓"
        elif state == "failed":
            mark = "!"
        text = text + '<div class="dt-pipe-stage ' + state + '"><span class="mark">' + mark + "</span>" + STAGE_LABELS[index] + "</div>"
    text = text + "</div>"
    if status:
        text = text + '<div class="dt-pipe-status" role="status" aria-live="polite">' + html.escape(status) + "</div>"
    text = text + "</div>"
    return text


def summary(rows, stats):
    counts = {STATUS_VERIFIED: 0, STATUS_REVIEW: 0, STATUS_FLAGGED: 0}
    for row in rows:
        counts[row["status"]] = counts[row["status"]] + 1

    meta = str(stats["papers"]) + (" paper" if stats["papers"] == 1 else " papers")
    meta = meta + " · " + str(stats["seconds"]) + " s"
    if stats["papers_from_cache"] > 0:
        meta = meta + " · " + str(stats["papers_from_cache"]) + " reused"

    text = '<div class="dt-summary">'
    text = text + '<span class="count">' + str(len(rows)) + (" value" if len(rows) == 1 else " values") + "</span>"
    text = text + '<div class="dt-thinbar" role="img" aria-label="' + str(counts[STATUS_VERIFIED]) + " verified, "
    text = text + str(counts[STATUS_REVIEW]) + " to review, " + str(counts[STATUS_FLAGGED]) + ' flagged">'
    text = text + '<span class="v" style="flex:' + str(counts[STATUS_VERIFIED]) + '"></span>'
    text = text + '<span class="r" style="flex:' + str(counts[STATUS_REVIEW]) + '"></span>'
    text = text + '<span class="f" style="flex:' + str(counts[STATUS_FLAGGED]) + '"></span></div>'
    text = text + '<span class="dt-legend">'
    text = text + '<span><i style="background:var(--verified)"></i>' + str(counts[STATUS_VERIFIED]) + " verified</span>"
    text = text + '<span><i style="background:var(--review)"></i>' + str(counts[STATUS_REVIEW]) + " to review</span>"
    text = text + '<span><i style="background:var(--flagged)"></i>' + str(counts[STATUS_FLAGGED]) + " flagged</span>"
    text = text + "</span>"
    text = text + '<span class="dt-meta">' + html.escape(meta) + "</span>"
    text = text + "</div>"
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

    text = '<div class="dt-card">'
    text = text + '<div class="dt-card-sub">' + html.escape(str(row["material"])) + ", " + html.escape(str(property_name)) + "</div>"
    text = text + '<div class="dt-card-value">' + value_text + '<span class="unit">' + html.escape(str(row["unit"])) + "</span></div>"
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
