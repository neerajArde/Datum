# schema.py
# what ONE row of the datum table looks like.
# every part of the app (llm prompt, verify, table, csv) uses these same names,
# so if we ever add a column we add it here and nowhere else.

# bump this whenever the prompt changes, so the cache doesnt hand back old answers
PROMPT_VERSION = "v3"

# the fields we ask the llm to fill in for every measurement
LLM_FIELDS = [
    "material",    # material name exactly as the paper writes it
    "property",    # which target property this value is
    "value",       # the number, copied exactly
    "error",       # the +/- part, or ""
    "unit",        # unit exactly as written
    "page",        # page number the evidence is on
    "evidence",    # the exact sentence / table row the value came from
    "conditions",  # how it was made or tested (electrolyte, thickness...), or ""
    "origin",      # "this paper" or "cited" (copied from another paper)
]

# the three possible verdicts after verification, from best to worst
STATUS_VERIFIED = "verified"
STATUS_REVIEW = "review"
STATUS_FLAGGED = "flagged"

# the columns of the final table, in the order the user sees them
TABLE_COLUMNS = [
    "status",
    "material",
    "property",
    "property_std",  # which of the user's target properties this row belongs to
    "value",
    "error",
    "unit",
    "value_std",   # value converted to a standard unit (if we know the unit)
    "error_std",
    "unit_std",
    "conditions",
    "origin",
    "paper",
    "page",
    "evidence",
    "checks",      # plain-english notes from verification
    "provider",    # which llm extracted it (gemini / claude / openai)
]


def clean_llm_row(raw):
    # the llm can return anything (numbers, null, missing keys),
    # so we force every field into a plain trimmed string
    row = {}
    for field in LLM_FIELDS:
        value = raw.get(field, "")
        if value is None:
            value = ""
        row[field] = str(value).strip()
    return row
