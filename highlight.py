# highlight.py
# click-to-source: draw the paper's page with the evidence highlighted in yellow,
# so anyone can SEE where a number came from.

import pymupdf

# how much page to show above and below the highlight (in pdf points)
MARGIN = 140


def search_candidates(evidence, value):
    # pdfs break lines in odd places, so if the full evidence isnt found
    # we try shorter pieces of it, and finally just the value
    candidates = []
    evidence = " ".join(str(evidence).split())
    if len(evidence) > 0:
        candidates.append(evidence)
    if len(evidence) > 60:
        candidates.append(evidence[:60])
    if len(evidence) > 30:
        candidates.append(evidence[:30])
    if len(str(value).strip()) > 0:
        candidates.append(str(value).strip())
    return candidates


def render_evidence(pdf_bytes, page_number, evidence, value, zoom=2.0, crop=True):
    # returns (png bytes, how it was found: "evidence" / "value only" / "not found")
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        index = int(page_number) - 1
        if index < 0 or index >= len(doc):
            return None, "not found"
        page = doc[index]

        rects = []
        how = "not found"
        candidates = search_candidates(evidence, value)
        for number in range(len(candidates)):
            rects = page.search_for(candidates[number])
            if len(rects) > 0:
                if number == len(candidates) - 1 and len(candidates) > 1:
                    how = "value only"
                else:
                    how = "evidence"
                break

        for rect in rects:
            page.add_highlight_annot(rect)

        # crop to the area around the highlight, so the evidence is easy to see
        clip = page.rect
        if crop and len(rects) > 0:
            top = min(r.y0 for r in rects) - MARGIN
            bottom = max(r.y1 for r in rects) + MARGIN
            clip = pymupdf.Rect(page.rect.x0, max(page.rect.y0, top), page.rect.x1, min(page.rect.y1, bottom))

        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip, annots=True)
        return pixmap.tobytes("png"), how
    finally:
        doc.close()
