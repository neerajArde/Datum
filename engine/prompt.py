# prompt.py
# the instructions we give the llm. one prompt for every provider,
# so gemini, claude and openai all return the exact same shape.
# if you change this file, bump PROMPT_VERSION in schema.py.


def build_prompt(chunk_text, target_properties):
    prompt = ""
    prompt = prompt + "You are a careful data extractor for materials science papers.\n\n"

    prompt = prompt + "TARGET PROPERTIES: " + target_properties + "\n\n"

    prompt = prompt + "The text below was extracted from a PDF. "
    prompt = prompt + "Each page starts with a marker like '=== PAGE 4 ==='. "
    prompt = prompt + "Tables may appear as one cell per line.\n\n"

    prompt = prompt + "Extract every measured value of a TARGET PROPERTY that is stated in the text.\n"
    prompt = prompt + "Rules:\n"
    prompt = prompt + "- Only extract the target properties. Ignore every other number.\n"
    prompt = prompt + "- One item per value. If a table row has two target properties, make two items.\n"
    prompt = prompt + "- If a table has SEVERAL columns for the same property (e.g. a calculated 'µC*' and a "
    prompt = prompt + "measured '[µC*]OECT'), put that column's exact header in 'property' so they can be told apart.\n"
    prompt = prompt + "- Keep the material name exactly as printed, including qualifiers like '[VPP]'.\n"
    prompt = prompt + "- Copy values exactly as written. Never calculate, convert, round or guess.\n"
    prompt = prompt + "- 'evidence' must be copied character for character from the text: the sentence or "
    prompt = prompt + "table row that contains the value. Keep it under 300 characters.\n"
    prompt = prompt + "- 'page' is the number in the nearest '=== PAGE n ===' marker above the evidence.\n"
    prompt = prompt + "- 'unit': if a table gives the unit in its header, use that unit.\n"
    prompt = prompt + "- The unit must fit the property. Example: a capacitance per AREA (F/cm2) is NOT "
    prompt = prompt + "a volumetric capacitance (F/cm3). Skip values whose unit does not fit.\n"
    prompt = prompt + "- 'material': the material name ONLY. PDFs often glue a citation number onto a name "
    prompt = prompt + "(e.g. 'PEDOT:PSS + EG19' = material 'PEDOT:PSS + EG' + citation 19). Remove it from the name.\n"
    prompt = prompt + "- 'reference': that citation number (e.g. '19'), or '' if the value has no citation.\n"
    prompt = prompt + "- 'value' is the number only and 'error' is the part after ±. '241 ± 94' -> value '241', error '94'.\n"
    prompt = prompt + "- 'origin': 'cited' if the value has a citation or the text says it was taken from another "
    prompt = prompt + "work, otherwise 'this paper'.\n"
    prompt = prompt + "- 'conditions': how the sample was made or tested (processing, electrolyte, "
    prompt = prompt + "thickness, voltage...), only if stated. Otherwise ''.\n"
    prompt = prompt + "- If nothing matches, return {\"rows\": []}.\n\n"

    prompt = prompt + "Return ONLY a JSON object with this exact shape, no other text:\n"
    prompt = prompt + "{\"rows\": [{\"material\": \"\", \"property\": \"\", \"value\": \"\", "
    prompt = prompt + "\"error\": \"\", \"unit\": \"\", \"page\": 0, \"evidence\": \"\", "
    prompt = prompt + "\"conditions\": \"\", \"origin\": \"this paper\", \"reference\": \"\"}]}\n\n"

    prompt = prompt + "TEXT:\n"
    prompt = prompt + chunk_text
    return prompt
