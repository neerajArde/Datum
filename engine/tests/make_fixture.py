# make_fixture.py
# builds a small fake "paper" pdf for the tests, laid out like a real
# supplementary file: one value per table cell, ± and µ characters, a references page.
# values match the 2018 crystallized PEDOT:PSS supplementary table.

import pymupdf


def write_line(page, y, cells):
    # cells = [(x position, text), ...] all on the same line, like a table row
    for x, text in cells:
        page.insert_text((x, y), text, fontname="helv", fontsize=10)


def build_fixture():
    doc = pymupdf.open()

    # page 1: intro (mentions the device but no target property words)
    page = doc.new_page()
    write_line(page, 72, [(72, "Supplementary Information")])
    write_line(page, 100, [(72, "Highly crystallized PEDOT:PSS films for organic electrochemical transistors.")])
    write_line(page, 116, [(72, "Supplementary Figure 1. X-ray diffraction patterns of a pristine film.")])

    # page 2: the uC* / C* table
    page = doc.new_page()
    write_line(page, 72, [(72, "Supplementary Table 1. Volumetric capacitance and figure of merit.")])
    write_line(page, 100, [(72, "Materials/Formulation"), (260, "C* (F cm-3)"), (380, "[µC*]OECT (F cm-1V-1s-1)")])
    write_line(page, 120, [(72, "PEDOT:Tos"), (260, "136 ± 50"), (380, "72 ± 14")])
    write_line(page, 140, [(72, "PEDOT:PSS + EG"), (260, "39 ± 3"), (380, "47 ± 6")])
    write_line(page, 160, [(72, "EG-P (Our result)"), (260, "31 ± 0.79"), (380, "100 ± 7")])
    write_line(page, 180, [(72, "Crys-P"), (260, "113 ± 1.38"), (380, "490 ± 41")])
    write_line(page, 210, [(72, "The data of PEDOT:Tos and PEDOT:PSS + EG were adopted from [1].")])

    # page 3: conductivity table
    page = doc.new_page()
    write_line(page, 72, [(72, "Supplementary Table 2. Electrical conductivity of PEDOT:PSS films.")])
    write_line(page, 100, [(72, "Materials"), (260, "Electrical conductivity (S/cm)")])
    write_line(page, 120, [(72, "Pr-P"), (260, "1.7 ± 0.12")])
    write_line(page, 140, [(72, "EG-P"), (260, "590 ± 20")])
    write_line(page, 160, [(72, "Crys-P"), (260, "4100 ± 98")])

    # page 4: references (should be skipped by the relevance filter)
    page = doc.new_page()
    write_line(page, 72, [(72, "References")])
    write_line(page, 100, [(72, "1. Inal, S., Malliaras, G. G. & Rivnay, J. Nat. Commun. 8, 1767 (2017).")])

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


if __name__ == "__main__":
    with open("fixture_paper.pdf", "wb") as file:
        file.write(build_fixture())
    print("wrote fixture_paper.pdf")
