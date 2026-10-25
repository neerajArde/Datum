# Datum

**Turn materials papers into a dataset where every number traces back to its source.**

Researchers build datasets by copying measurements out of papers by hand. It's slow and error-prone, and sources and experimental conditions get lost along the way. Datum reads the papers with an LLM, then **checks every value against the PDF with plain code**. Each number in the table comes with its evidence sentence, its page and a verdict:

| Status | Meaning |
|---|---|
| ✅ verified | evidence exists in the paper and contains the value |
| 🟡 review | probably right, worth a glance (cited from another paper, approximate match, no unit…) |
| 🚩 flagged | failed a hard check: evidence not in the paper, or value not in the evidence (likely hallucination) |

Built at HackPSU Fall 2026 by team **Ground Truth**.

## How it works

```
PDFs → 1 Ingest → 2 Filter + chunk → 3 Extract (parallel) → 4 Verify → 5 Table / CSV / evidence viewer
                                          │
                                   provider router
                              Gemini → Claude → OpenAI
```

1. **Ingest** (`ingest.py`): reads each PDF page by page and fingerprints it by content.
2. **Filter + chunk** (`ingest.py`): skips pages that never mention a target property (references, acknowledgements) and groups the rest a few pages per AI call, with `=== PAGE n ===` markers.
3. **Extract** (`pipeline.py`, `providers.py`, `prompt.py`): runs chunks from all papers in parallel. The router tries Gemini first. If a provider is busy (429/503/timeout), it cools down and the router hops to the next. If a provider is broken (bad key or model), it's switched off for the run. If an answer gets cut off, the chunk is split in half and retried.
4. **Verify** (`verify.py`, `units.py`): no LLM here. It checks that the evidence exists in the paper (fixing wrong page numbers), that the value is inside the evidence, the material, unit and origin, and converts units to a standard form.
5. **Results** (`app.py`, `highlight.py`, `evaluate.py`): a filterable table, click-to-source page highlighting, CSV export, and an accuracy check against a hand-made answer key.

Answers are cached by paper content (`cache.py`), so re-running a paper is instant and makes no API calls.

## Run it

```bash
pip install -r requirements.txt
# set at least one key. engines are tried in this order:
export CEREBRAS_API_KEY="..."        # free, very fast (cloud.cerebras.ai)
export GEMINI_API_KEY="..."          # free tier (Google AI Studio)
export GROQ_API_KEY="..."            # free, fast (console.groq.com)
export ANTHROPIC_API_KEY="..."       # paid backup (console.anthropic.com)
export OPENAI_API_KEY="..."          # paid backup (platform.openai.com)
python -m streamlit run app.py
```

Model names can be changed without touching code by setting `CEREBRAS_MODEL`, `GEMINI_MODEL`, `GROQ_MODEL`, `CLAUDE_MODEL` or `OPENAI_MODEL`.

On Streamlit Community Cloud, put the same keys in the app's **Secrets**.

## Tests

```bash
python -m pytest -q
```

The tests use a fake LLM, so they need no key and no internet. They cover provider fallback, hallucination flagging, page correction, unit conversion, caching, cut-off answers and the accuracy report.

## Accuracy check

Download the blank answer key in the app, fill in the true values for a few papers (`material, property, value`) and upload it. Datum reports:
- **precision:** how many extracted values were right
- **recall:** how many true values it found
- **errors caught:** how many of its wrong values verification had already marked review or flagged
