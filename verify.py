# verify.py
# stage 4: the trust layer. plain code, NO llm.
#
# the llm is a fast reader that sometimes makes things up (hallucinations).
# this file checks every row it produced against the actual pdf text:
#   1. does the evidence sentence really exist in the paper? on which page?
#   2. is the value really inside that evidence?
#   3. is anything missing (unit, material)? was the value copied from another paper?
#   4. convert units to one standard form
#
# every row ends up with a status:
#   verified  - all checks passed
#   review    - probably fine, but a human should glance at it
#   flagged   - failed a hard check, likely a hallucination

import re

from rapidfuzz import fuzz

from schema import STATUS_FLAGGED, STATUS_REVIEW, STATUS_VERIFIED, TABLE_COLUMNS
from text_tools import join_scientific, normalize, numbers_in, same_material_name, same_number, squash, to_number
from units import expected_unit, standardize

# how similar (0-100) a property name must be to one of the user's target properties
PROPERTY_MATCH_SCORE = 75

# how similar (0-100) the evidence must be to the page text when not an exact match
EVIDENCE_MATCH_SCORE = 90
MATERIAL_MATCH_SCORE = 85

# evidence shorter than this is too short to prove anything ("490" matches everywhere)
MIN_EVIDENCE_CHARS = 12

# order of how bad each status is
SEVERITY = {STATUS_VERIFIED: 0, STATUS_REVIEW: 1, STATUS_FLAGGED: 2}


def worse(current, new):
    # keep whichever status is worse
    if SEVERITY[new] > SEVERITY[current]:
        return new
    return current


def page_number(value):
    try:
        return int(float(str(value).strip()))
    except Exception:
        return None


def find_evidence(evidence, pages, claimed_page):
    # look for the evidence in the paper. check the page the llm claimed first,
    # then every other page (the llm sometimes gets the page number wrong).
    # returns (page it was found on or None, "exact" / "close" / "")
    target = normalize(evidence)

    order = []
    for page_info in pages:
        if page_info["page"] == claimed_page:
            order.insert(0, page_info)
        else:
            order.append(page_info)

    normalized_pages = []
    for page_info in order:
        normalized_pages.append((page_info["page"], normalize(page_info["text"])))

    # pass 1: exact match (after cleaning spaces, dashes, µ/μ...)
    for number, text in normalized_pages:
        if target in text:
            return number, "exact"

    # pass 2: close match (the llm changed a character or two)
    for number, text in normalized_pages:
        score = fuzz.partial_ratio(target, text)
        if score >= EVIDENCE_MATCH_SCORE:
            return number, "close"

    return None, ""


def split_targets(target_properties):
    # "μC*, volumetric capacitance C*" -> ["μC*", "volumetric capacitance C*"]
    text = str(target_properties or "")
    for separator in [";", "\n"]:
        text = text.replace(separator, ",")
    targets = []
    for part in text.split(","):
        part = part.strip()
        if part != "":
            targets.append(part)
    return targets


def match_target(prop, targets):
    # which of the user's properties is this? returns (target, score)
    # "C*" -> "volumetric capacitance C*", "µC*" -> "μC*", "µOECT" -> no match
    p = normalize(prop)
    best_target = ""
    best_score = 0
    for target in targets:
        t = normalize(target)
        score = max(fuzz.ratio(p, t), fuzz.token_set_ratio(p, t))
        # partial matching only for names of 3+ characters, otherwise "c*" matches everything
        if min(len(p), len(t)) >= 3:
            score = max(score, fuzz.partial_ratio(p, t))
        if score > best_score:
            best_score = score
            best_target = target
    return best_target, best_score


# how far back from a value we look for its row's material name (in characters, spaces removed)
TABLE_ROW_REACH = 200
NUMBER_IN_TEXT = re.compile(r"-?\d+(?:\.\d+)?(?:e[-+]?\d+)?")


def is_table_like(evidence, material):
    # a table row is a name followed by numbers: "PEDOT:PSS + EG 39 ± 3 1.9 ± 1.3 47 ± 6".
    # a sentence has real words: "Pr-P shows a conductivity of 1.7 S/cm in water".
    # sentences must be found word for word; table rows get the table check below.
    material_words = re.findall(r"[^\W\d_]{2,}", normalize(material))
    extra = 0
    for word in re.findall(r"[^\W\d_]{2,}", normalize(evidence)):
        if word not in material_words:
            extra = extra + 1
    return extra <= 2


def name_pattern(name):
    # "PEDOT:PSS + EG" -> a pattern that also matches "PEDOT:PSS+EG" (spacing varies in pdfs)
    squashed = squash(name)
    if squashed == "":
        return None
    parts = []
    for character in squashed:
        parts.append(re.escape(character))
    return re.compile(r"\s*".join(parts))


def find_table_row(material, value, error, pages, claimed_page, known_materials):
    # for tables, pdf text stores one cell per line, so the ai's "row" is never an exact quote.
    # instead we check the facts directly on the page:
    #   - the value (and its ± error) is printed on the page
    #   - the CLOSEST material name before it is this row's material
    #     (closest, so a value can't be credited to the material in the row above)
    number = to_number(value)
    if number is None or squash(material) == "":
        return None
    error_number = to_number(error)

    names = []
    seen = []
    for name in list(known_materials) + [material]:
        if squash(name) in seen or squash(name) == "":
            continue
        seen.append(squash(name))
        names.append((name, name_pattern(name)))

    order = []
    for page_info in pages:
        if page_info["page"] == claimed_page:
            order.insert(0, page_info)
        else:
            order.append(page_info)

    for page_info in order:
        # cells stay separated by spaces, so "EG19" and "39" never merge into "1939"
        text = join_scientific(normalize(page_info["text"]))
        text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)
        for match in NUMBER_IN_TEXT.finditer(text):
            # a whole number only: dont match the "9" inside "19" or "1.9"
            before = text[match.start() - 1:match.start()] if match.start() > 0 else ""
            if before.isdigit() or before == ".":
                continue
            if not same_number(float(match.group()), number):
                continue
            if error_number is not None:
                after = text[match.end():match.end() + 20].lstrip()
                if not after.startswith("±"):
                    continue
                following = NUMBER_IN_TEXT.match(after[1:].lstrip())
                if following is None or not same_number(float(following.group()), error_number):
                    continue

            # which material name sits closest before this value?
            window_start = max(0, match.start() - TABLE_ROW_REACH)
            window = text[window_start:match.start()]
            closest_name = ""
            closest_end = -1
            closest_length = 0
            # the name that ENDS closest to the value wins. this also picks "PEDOT:PSS + EG"
            # over "PEDOT:PSS" in the same spot, because the longer name ends later
            for name, pattern in names:
                for found in pattern.finditer(window):
                    closer = found.end() > closest_end
                    same_spot_longer = found.end() == closest_end and len(found.group()) > closest_length
                    if closer or same_spot_longer:
                        closest_end = found.end()
                        closest_length = len(found.group())
                        closest_name = name
            if closest_name == "":
                continue
            if same_material_name(closest_name, material):
                return page_info["page"]
    return None


def number_is_in(number, text):
    for found in numbers_in(text):
        if same_number(found, number):
            return True
    return False


def split_plus_minus(value, error):
    # "241 ± 94" -> ("241", "94"). done in plain code so it works the same every time,
    # whatever the ai did. only splits when the error field is empty
    text = str(value)
    if error != "":
        return value, error
    for sign in ["±", "+/-", "+-"]:
        if sign in text:
            parts = text.split(sign, 1)
            return parts[0].strip(), parts[1].strip()
    return value, error


def verify_row(raw, pages, paper_name, target_properties="", known_materials=None):
    checks = []
    status = STATUS_VERIFIED

    material = raw.get("material", "")
    value, error = split_plus_minus(raw.get("value", ""), raw.get("error", ""))
    unit = raw.get("unit", "")
    evidence = raw.get("evidence", "")
    origin = raw.get("origin", "")
    reference = raw.get("reference", "").strip().strip("[]()").strip()
    if reference != "":
        origin = "cited"
    claimed_page = page_number(raw.get("page", ""))
    final_page = claimed_page

    # --- missing basics ---
    if material == "":
        status = worse(status, STATUS_FLAGGED)
        checks.append("no material name")
    if value == "":
        status = worse(status, STATUS_FLAGGED)
        checks.append("no value")

    # --- check 1: does the evidence exist in the paper? ---
    evidence_found = False
    if len(normalize(evidence)) < MIN_EVIDENCE_CHARS:
        status = worse(status, STATUS_FLAGGED)
        checks.append("evidence too short to check")
    else:
        found_page, how = find_evidence(evidence, pages, claimed_page)
        if found_page is None and is_table_like(evidence, material):
            found_page = find_table_row(material, value, error, pages, claimed_page, known_materials or [])
            if found_page is not None:
                how = "table"
                checks.append("matched as a table row (material and value found together on the page)")
        if found_page is None:
            status = worse(status, STATUS_FLAGGED)
            checks.append("evidence not found in paper (possible hallucination)")
        else:
            evidence_found = True
            if how == "close":
                status = worse(status, STATUS_REVIEW)
                checks.append("evidence only approximately matches the paper")
            if claimed_page != found_page:
                checks.append("page corrected from " + str(claimed_page) + " to " + str(found_page))
                final_page = found_page

    # --- check 2: is the value really inside the evidence? ---
    value_number = to_number(value)
    if value != "":
        if value_number is None:
            status = worse(status, STATUS_REVIEW)
            checks.append("value is not a single number")
        elif evidence_found and not number_is_in(value_number, evidence):
            status = worse(status, STATUS_FLAGGED)
            checks.append("value not in evidence (possible hallucination)")

    error_number = to_number(error)
    if error != "" and error_number is not None and evidence_found:
        if not number_is_in(error_number, evidence):
            status = worse(status, STATUS_REVIEW)
            checks.append("error value not in evidence")

    # --- check 3: other things a researcher should know ---
    if material != "" and evidence_found:
        score = fuzz.partial_ratio(normalize(material), normalize(evidence))
        if score < MATERIAL_MATCH_SCORE:
            # papers often name the material one sentence earlier, so this is a note, not a problem
            checks.append("material named outside the evidence sentence")

    if unit == "":
        status = worse(status, STATUS_REVIEW)
        checks.append("no unit")

    # where the number originally comes from is shown in its own column.
    # it does NOT lower the status: status only answers "is this number really in this paper?"
    if reference != "":
        checks.append("originally reported in reference [" + reference + "] of this paper")
    elif "cite" in origin.lower():
        checks.append("originally reported in another paper")

    property_std = ""
    targets = split_targets(target_properties)
    if len(targets) > 0 and raw.get("property", "") != "":
        target, score = match_target(raw.get("property", ""), targets)
        if score >= PROPERTY_MATCH_SCORE:
            property_std = target
        else:
            status = worse(status, STATUS_REVIEW)
            checks.append("not one of your target properties")

    if raw.get("conditions", "") == "":
        checks.append("no conditions stated")

    # --- check 4: standard units, and does the unit fit the property? ---
    value_std, error_std, unit_std, unit_note = standardize(value_number, error_number, unit)
    if unit_note != "":
        checks.append(unit_note)

    should_be = expected_unit(property_std or raw.get("property", ""))
    if should_be != "" and unit_std != "" and unit_std != should_be:
        status = worse(status, STATUS_REVIEW)
        checks.append("unit " + unit_std + " doesn't fit this property (expected " + should_be + ")")

    # build the final row key by key, in table order
    row = {}
    for column in TABLE_COLUMNS:
        row[column] = ""
    row["status"] = status
    row["material"] = material
    row["property"] = raw.get("property", "")
    row["property_std"] = property_std
    row["value"] = value
    row["error"] = error
    row["unit"] = unit
    row["value_std"] = value_std
    row["error_std"] = error_std
    row["unit_std"] = unit_std
    row["conditions"] = raw.get("conditions", "")
    row["origin"] = origin
    row["reference"] = reference
    row["paper"] = paper_name
    row["page"] = final_page  # None if we never found a page
    row["evidence"] = evidence
    row["checks"] = "; ".join(checks)
    row["provider"] = raw.get("provider", "")
    return row
