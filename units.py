# units.py
# papers write the same unit in different ways: "S/cm", "S cm-1", "S cm⁻¹"
# and sometimes use a different scale: S/m instead of S/cm.
# this file turns them into ONE standard form so values from different papers
# can sit in the same column and actually be compared.
#
# if a unit isnt in our list we dont guess - we leave it as written and say so.

import re
import unicodedata

from text_tools import DASHES

# readable unit -> (standard unit, multiply by this to get the standard unit)
# add new units here, nothing else needs to change
KNOWN_UNITS = {
    # electrical conductivity
    "S/cm": ("S/cm", 1.0),
    "S/m": ("S/cm", 0.01),
    "mS/cm": ("S/cm", 0.001),
    "kS/cm": ("S/cm", 1000.0),
    # volumetric capacitance C* (per volume)
    "F/cm3": ("F/cm³", 1.0),
    "F/m3": ("F/cm³", 1e-6),
    # areal capacitance (per AREA - a different quantity from C*)
    "F/cm2": ("F/cm²", 1.0),
    "mF/cm2": ("F/cm²", 1e-3),
    "μF/cm2": ("F/cm²", 1e-6),
    # the OECT figure of merit μC*
    "F cm-1 V-1 s-1": ("F cm⁻¹ V⁻¹ s⁻¹", 1.0),
    # mobility
    "cm2 V-1 s-1": ("cm² V⁻¹ s⁻¹", 1.0),
    # transconductance (careful: capital S = siemens)
    "S": ("mS", 1000.0),
    "mS": ("mS", 1.0),
    "μS": ("mS", 0.001),
    # time (lowercase s = seconds), e.g. response time
    "s": ("ms", 1000.0),
    "ms": ("ms", 1.0),
    "μs": ("ms", 0.001),
}


def split_power(token):
    # "cm-3" -> ("cm", -3), "cm3" -> ("cm", 3), "cm" -> ("cm", 1)
    match = re.match(r"^([^\d-]+)(-?\d+)?$", token)
    if match is None:
        return token, 1
    base = match.group(1)
    power = match.group(2)
    if power is None:
        return base, 1
    return base, int(power)


def join_power(base, power):
    # ("cm", 1) -> "cm", ("cm", -3) -> "cm-3"
    if power == 1:
        return base
    return base + str(power)


def unit_key(unit):
    # build a compact, order-independent version of a unit for looking it up.
    # "S/cm", "S cm-1", "S cm⁻¹", "S·cm^-1" all become the same key.
    if unit is None:
        return ""
    text = unicodedata.normalize("NFKC", str(unit))   # ⁻¹ -> −1, µ -> μ
    for dash in DASHES:
        text = text.replace(dash, "-")
    for symbol in ["^", "(", ")", "[", "]"]:
        text = text.replace(symbol, "")
    for symbol in ["·", "*", "×", "⋅"]:
        text = text.replace(symbol, " ")
    text = text.strip()
    if text == "":
        return ""

    # "F/cm3" -> top "F", bottom "cm3". everything after "/" gets a negative power
    parts = text.split("/")
    top = parts[0].split()
    bottom = []
    for part in parts[1:]:
        bottom = bottom + part.split()

    tokens = []
    for token in top:
        base, power = split_power(token)
        tokens.append(join_power(base, power))
    for token in bottom:
        base, power = split_power(token)
        tokens.append(join_power(base, -power))

    # sort so "F V-1 cm-1 s-1" and "F cm-1 V-1 s-1" match
    tokens.sort()
    return " ".join(tokens)


# which standard unit a property SHOULD have, found by a word in the property name.
# if a row's unit is a known unit but the wrong kind, verification says so.
EXPECTED_UNITS = [
    ("volumetric", "F/cm³"),
    ("c*", "F/cm³"),
    ("conductivity", "S/cm"),
    ("mobility", "cm² V⁻¹ s⁻¹"),
    ("transconductance", "mS"),
]


def expected_unit(property_name):
    # "μC*" must be checked before "C*", so the figure of merit isnt read as capacitance
    name = unicodedata.normalize("NFKC", str(property_name)).lower()
    if "μc*" in name or "uc*" in name:
        return "F cm⁻¹ V⁻¹ s⁻¹"
    for word, unit in EXPECTED_UNITS:
        if word in name:
            return unit
    return ""


# build the lookup table once, using the same key function
LOOKUP = {}
for readable_unit in KNOWN_UNITS:
    LOOKUP[unit_key(readable_unit)] = KNOWN_UNITS[readable_unit]


def format_number(number):
    # 5.8999999999 -> "5.9", keep 6 significant digits
    return format(number, ".6g")


def standardize(value_number, error_number, unit):
    # returns (value_std, error_std, unit_std, note) as strings
    key = unit_key(unit)
    if key == "":
        return "", "", "", ""
    if key not in LOOKUP:
        return "", "", "", "unit not in standard list, kept as written"

    standard_unit, factor = LOOKUP[key]

    value_std = ""
    if value_number is not None:
        value_std = format_number(value_number * factor)

    error_std = ""
    if error_number is not None:
        error_std = format_number(error_number * factor)

    note = ""
    if factor != 1.0:
        note = "converted " + str(unit).strip() + " to " + standard_unit

    return value_std, error_std, standard_unit, note
