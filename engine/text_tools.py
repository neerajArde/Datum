# text_tools.py
# small helpers that make text from pdfs comparable.
# pdfs are messy: weird dashes, line breaks in the middle of sentences,
# two different "micro" characters that look identical (µ vs μ)...

import re
import unicodedata

# all the dash-looking characters pdfs use for "minus"
DASHES = ["−", "–", "—", "‐", "‑"]

# matches numbers like 490, 1.38, -0.5, 1.7e3
NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")

# scientific notation the way papers print it (after normalize):
#   "6.61 x 10-4", "6.61 x 10^-4", "6.61x10-4", "6.61 * 10-4", "6.61 · 10 -4", "6.61 x 10^(-4)"
# the pdf loses the superscript, so "10⁻⁴" arrives as "10-4"
SCIENTIFIC_PATTERN = re.compile(r"(-?\d+(?:\.\d+)?)\s*(?:x|\*|·)\s*10\s*\^?\s*\(?\s*([-+]?)\s*(\d{1,3})\s*\)?(?!\d)")


def normalize(text):
    # turn text into one standard form so two copies of the same sentence match
    if text is None:
        return ""
    text = str(text)

    # nfkc merges look-alike characters: µ (micro sign) -> μ (greek mu),
    # superscript ¹ -> 1, and so on
    text = unicodedata.normalize("NFKC", text)

    # every kind of dash becomes a normal "-"
    for dash in DASHES:
        text = text.replace(dash, "-")

    # "×" and "x" mean the same in "6.61 × 10-4"; "^" is dropped in some copies and kept in others
    text = text.replace("×", "x").replace("^", "")

    # squash line breaks, tabs and double spaces into single spaces
    words = text.split()
    text = " ".join(words)

    return text.lower()


def join_scientific(text):
    # "6.61 x 10-4" -> "6.61e-4", so it reads as ONE number instead of 6.61, 10 and -4.
    # expects normalized text
    def to_e(match):
        return match.group(1) + "e" + (match.group(2) or "") + match.group(3)
    return SCIENTIFIC_PATTERN.sub(to_e, text)


def numbers_in(text):
    # pull every number out of a piece of text, as floats
    text = join_scientific(normalize(text))

    # remove thousands commas: 4,100 -> 4100 (only when a comma sits between digits)
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)

    found = []
    for match in NUMBER_PATTERN.findall(text):
        try:
            found.append(float(match))
        except ValueError:
            pass
    return found


def to_number(value):
    # "490" -> 490.0, "4,100" -> 4100.0
    # returns None if the value isnt exactly one number (like "100-200" or "high")
    numbers = numbers_in(value)
    if len(numbers) != 1:
        return None
    return numbers[0]


def same_number(a, b):
    # floats can be slightly off after maths, so allow a tiny RELATIVE difference
    # (relative, so 1e-12 and 2e-12 are different numbers, while 6.61e-4 and 0.000661 are the same)
    if a == b:
        return True
    return abs(a - b) <= 1e-9 * max(abs(a), abs(b))


def squash(name):
    # material names compared without spaces or case: "PEDOT:PSS + EG" -> "pedot:pss+eg"
    return normalize(name).replace(" ", "")


def same_material_name(a, b):
    # material names must match EXACTLY - "p(g2T-TT)" and "p(g2T-T)" are different polymers.
    # the one allowed difference: a citation number glued on the end by the pdf,
    # e.g. "PEDOT:PSS + EG19" is "PEDOT:PSS + EG" from reference 19
    a = squash(a)
    b = squash(b)
    if a == "" or b == "":
        return False
    if a == b:
        return True
    if re.fullmatch(re.escape(a) + r"\d{1,3}", b):
        return True
    if re.fullmatch(re.escape(b) + r"\d{1,3}", a):
        return True
    return False
