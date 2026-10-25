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
    prompt = prompt + "- Copy values exactly as written. Never calculate, convert, round or guess.\n"
    prompt = prompt + "- 'evidence' must be copied character for character from the text: the sentence or "
    prompt = prompt + "table row that contains the value. Keep it under 300 characters.\n"
    prompt = prompt + "- 'page' is the number in the nearest '=== PAGE n ===' marker above the evidence.\n"
    prompt = prompt + "- 'unit': if a table gives the unit in its header, use that unit.\n"
    prompt = prompt + "- The unit must fit the property. Example: a capacitance per AREA (F/cm2) is NOT "
    prompt = prompt + "a volumetric capacitance (F/cm3). Skip values whose unit does not fit.\n"
    prompt = prompt + "- 'origin': 'this paper' if the authors measured it, 'cited' if the text says "
    prompt = prompt + "the value was taken or adopted from another work.\n"
    prompt = prompt + "- 'conditions': how the sample was made or tested (processing, electrolyte, "
    prompt = prompt + "thickness, voltage...), only if stated. Otherwise ''.\n"
    prompt = prompt + "- If nothing matches, return {\"rows\": []}.\n\n"

    prompt = prompt + "Return ONLY a JSON object with this exact shape, no other text:\n"
    prompt = prompt + "{\"rows\": [{\"material\": \"\", \"property\": \"\", \"value\": \"\", "
    prompt = prompt + "\"error\": \"\", \"unit\": \"\", \"page\": 0, \"evidence\": \"\", "
    prompt = prompt + "\"conditions\": \"\", \"origin\": \"this paper\"}]}\n\n"

    prompt = prompt + "TEXT:\n"
    prompt = prompt + chunk_text
    return prompt
