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

    # squash line breaks, tabs and double spaces into single spaces
    words = text.split()
    text = " ".join(words)

    return text.lower()


def numbers_in(text):
    # pull every number out of a piece of text, as floats
    text = normalize(text)

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
    # floats can be slightly off after maths, so allow a tiny difference
    difference = abs(a - b)
    allowed = 1e-9 * max(1.0, abs(a), abs(b))
    return difference <= allowed
