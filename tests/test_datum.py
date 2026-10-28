# test_datum.py
# run with:  python -m pytest -q
# these tests use a FAKE llm (no api key, no internet), so they are fast and
# always give the same answer. they check that our own code does the right thing:
# routing, verification, units, caching, accuracy, highlighting.

import json
import os
import sys

import pandas as pd
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import cache  # noqa: E402
import pipeline  # noqa: E402
import providers  # noqa: E402
from evaluate import evaluate, read_answer_key  # noqa: E402
from highlight import render_evidence  # noqa: E402
from ingest import make_chunks, property_words, read_pages  # noqa: E402
from make_fixture import build_fixture  # noqa: E402
from units import standardize, unit_key  # noqa: E402

PROPERTIES = "μC*, volumetric capacitance C*, electrical conductivity"


def row(material, prop, value, error, unit, page, evidence, origin="this paper"):
    item = {}
    item["material"] = material
    item["property"] = prop
    item["value"] = value
    item["error"] = error
    item["unit"] = unit
    item["page"] = page
    item["evidence"] = evidence
    item["conditions"] = ""
    item["origin"] = origin
    return item


# what a (slightly unreliable) llm would answer for each page of the fixture
PAGE_2_ROWS = [
    row("PEDOT:Tos", "μC*", "72", "14", "F cm-1 V-1 s-1", 2, "PEDOT:Tos 136 ± 50 72 ± 14", "cited"),
    row("EG-P (Our result)", "μC*", "100", "7", "F cm-1 V-1 s-1", 2, "EG-P (Our result) 31 ± 0.79 100 ± 7"),
    # hallucination: the paper says 490, not 520
    row("Crys-P", "μC*", "520", "41", "F cm-1 V-1 s-1", 2, "Crys-P 113 ± 1.38 490 ± 41"),
    # right value, wrong page number from the llm (it is on page 2)
    row("Crys-P", "C*", "113", "1.38", "F cm-3", 3, "Crys-P 113 ± 1.38 490 ± 41"),
]
PAGE_3_ROWS = [
    row("Crys-P", "electrical conductivity", "4100", "98", "S/cm", 3, "Crys-P\n4100 ± 98"),
    # made-up evidence that is nowhere in the paper
    row("Pr-P", "electrical conductivity", "1.7", "", "S/cm", 3, "Pr-P shows a conductivity of 1.7 S/cm in water"),
]


def fake_answer(prompt):
    rows = []
    if "=== PAGE 2 ===" in prompt:
        rows = rows + PAGE_2_ROWS
    if "=== PAGE 3 ===" in prompt:
        rows = rows + PAGE_3_ROWS
    return json.dumps({"rows": rows})


class FakeHttpError(Exception):
    def __init__(self, status_code):
        super().__init__("http error " + str(status_code))
        self.status_code = status_code


def provider(name, call):
    item = {}
    item["name"] = name
    item["model"] = "fake"
    item["call"] = call
    return item


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    # every test gets its own empty cache folder and no real waiting
    monkeypatch.setattr(cache, "CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(providers.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(providers, "COOLDOWN_SECONDS", 0)


@pytest.fixture
def paper():
    item = {}
    item["name"] = "fixture.pdf"
    item["bytes"] = build_fixture()
    return item


def by_key(rows, material, prop):
    for item in rows:
        if item["material"] == material and item["property"] == prop:
            return item
    raise AssertionError("row not found: " + material + " " + prop)


# ---------------- ingest ----------------
def test_relevance_filter_skips_intro_and_references(paper):
    pages = read_pages(paper["bytes"])
    chunks, kept = make_chunks(pages, property_words(PROPERTIES), filter_pages=True)
    assert kept == 2
    assert chunks[0]["pages"] == [2, 3]


def test_scan_every_page_option_keeps_all_text_pages(paper):
    pages = read_pages(paper["bytes"])
    chunks, kept = make_chunks(pages, property_words(PROPERTIES), filter_pages=False)
    assert kept == 4


# ---------------- verification (through the full pipeline) ----------------
def test_pipeline_verifies_and_catches_hallucinations(paper):
    result = pipeline.run([paper], PROPERTIES, [provider("Fake", fake_answer)])
    rows = result["rows"]
    assert len(rows) == 6

    assert by_key(rows, "EG-P (Our result)", "μC*")["status"] == "verified"

    hallucinated = by_key(rows, "Crys-P", "μC*")
    assert hallucinated["status"] == "flagged"
    assert "value not in evidence" in hallucinated["checks"]

    wrong_page = by_key(rows, "Crys-P", "C*")
    assert wrong_page["page"] == 2
    assert "page corrected from 3 to 2" in wrong_page["checks"]

    # cited values are still verified (they ARE in this paper), origin is its own column
    cited = by_key(rows, "PEDOT:Tos", "μC*")
    assert cited["status"] == "verified"
    assert cited["origin"] == "cited"
    assert "originally reported in another paper" in cited["checks"]

    made_up = by_key(rows, "Pr-P", "electrical conductivity")
    assert made_up["status"] == "flagged"
    assert "evidence not found" in made_up["checks"]

    conductivity = by_key(rows, "Crys-P", "electrical conductivity")
    assert conductivity["status"] == "verified"
    assert conductivity["unit_std"] == "S/cm"
    assert conductivity["value_std"] == "4100"


# ---------------- router ----------------
def test_router_hops_to_next_provider_when_busy(paper):
    def busy(prompt):
        raise FakeHttpError(503)

    result = pipeline.run([paper], PROPERTIES, [provider("Busy", busy), provider("Backup", fake_answer)])
    assert len(result["rows"]) == 6
    assert result["stats"]["calls_by_provider"]["Backup"] == 1
    assert result["failures"] == []


def test_slow_provider_gets_raced_by_backup(paper, monkeypatch):
    import threading
    monkeypatch.setattr(providers, "HEDGE_SECONDS", 0.2)

    def slow(prompt):
        threading.Event().wait(3)   # a provider stuck for 3 seconds
        return fake_answer(prompt)

    start = __import__("time").perf_counter()
    result = pipeline.run([paper], PROPERTIES, [provider("Slow", slow), provider("Backup", fake_answer)])
    elapsed = __import__("time").perf_counter() - start

    assert len(result["rows"]) == 6
    assert result["stats"]["calls_by_provider"]["Backup"] == 1
    assert elapsed < 2      # we did NOT wait for the slow provider
    log = result["stats"]["call_log"]
    assert {"provider": "Backup", "outcome": "answered"}.items() <= log[0].items()


def test_call_log_names_the_problem(paper):
    def busy(prompt):
        raise FakeHttpError(429)

    result = pipeline.run([paper], PROPERTIES, [provider("Busy", busy), provider("Backup", fake_answer)])
    outcomes = [entry["outcome"] for entry in result["stats"]["call_log"]]
    assert "rate limited (429)" in outcomes
    assert "answered" in outcomes


def test_unreadable_answer_does_not_wait_for_slow_engine(paper, monkeypatch):
    import threading
    monkeypatch.setattr(providers, "HEDGE_SECONDS", 0.2)

    def stuck(prompt):
        threading.Event().wait(3)
        return fake_answer(prompt)

    def garbled_on_big_chunks(prompt):
        paper_text = prompt.split("TEXT:\n", 1)[1]
        if paper_text.count("=== PAGE") > 1:
            return "{\"rows\": [{\"mater"
        return fake_answer(prompt)

    start = __import__("time").perf_counter()
    result = pipeline.run([paper], PROPERTIES, [provider("Stuck", stuck), provider("Fast", garbled_on_big_chunks)])
    elapsed = __import__("time").perf_counter() - start
    assert len(result["rows"]) == 6
    assert elapsed < 2.5


def test_router_switches_off_broken_provider(paper):
    def broken(prompt):
        raise FakeHttpError(404)

    result = pipeline.run([paper], PROPERTIES, [provider("Broken", broken), provider("Backup", fake_answer)])
    assert "Broken" in result["stats"]["disabled_providers"]
    assert len(result["rows"]) == 6


def test_reports_failure_instead_of_crashing_when_everyone_is_down(paper):
    def busy(prompt):
        raise FakeHttpError(503)

    result = pipeline.run([paper], PROPERTIES, [provider("Busy", busy)])
    assert result["rows"] == []
    assert len(result["failures"]) == 1
    assert "all providers failed" in result["failures"][0]["reason"]


def test_cut_off_answer_gets_split_into_smaller_chunks(paper):
    def cuts_off_big_chunks(prompt):
        # only count the real page markers in the paper text, not the examples in the instructions
        paper_text = prompt.split("TEXT:\n", 1)[1]
        if paper_text.count("=== PAGE") > 1:
            return '{"rows": [{"material": "Crys-P", "val'
        return fake_answer(prompt)

    result = pipeline.run([paper], PROPERTIES, [provider("Fake", cuts_off_big_chunks)])
    assert len(result["rows"]) == 6
    assert result["failures"] == []


def test_parse_rows_handles_code_fences():
    text = "```json\n{\"rows\": [{\"material\": \"Crys-P\"}]}\n```"
    assert providers.parse_rows(text) == [{"material": "Crys-P"}]


# ---------------- cache ----------------
def test_second_run_uses_cache_and_makes_no_calls(paper):
    counter = {"calls": 0}

    def counting(prompt):
        counter["calls"] = counter["calls"] + 1
        return fake_answer(prompt)

    pipeline.run([paper], PROPERTIES, [provider("Fake", counting)])
    assert counter["calls"] == 1
    second = pipeline.run([paper], PROPERTIES, [provider("Fake", counting)])
    assert counter["calls"] == 1
    assert second["stats"]["papers_from_cache"] == 1
    assert len(second["rows"]) == 6


def test_failed_papers_are_not_cached(paper):
    def busy(prompt):
        raise FakeHttpError(503)

    pipeline.run([paper], PROPERTIES, [provider("Busy", busy)])
    second = pipeline.run([paper], PROPERTIES, [provider("Fake", fake_answer)])
    assert second["stats"]["papers_from_cache"] == 0
    assert len(second["rows"]) == 6


# ---------------- target properties ----------------
def test_property_names_map_to_targets():
    from verify import match_target, split_targets
    targets = split_targets("μC*, volumetric capacitance C*, electrical conductivity")
    cases = {
        "μC*": "μC*",
        "µC*": "μC*",                     # micro sign, as in the real paper
        "[µC*]OECT": "μC*",
        "C*": "volumetric capacitance C*",
        "volumetric capacitance": "volumetric capacitance C*",
        "conductivity": "electrical conductivity",
    }
    for written in cases:
        target, score = match_target(written, targets)
        assert target == cases[written] and score >= 75, written
    target, score = match_target("µOECT", targets)   # mobility: not asked for
    assert score < 75


def test_off_target_property_is_marked_for_review(paper):
    def with_extra(prompt):
        data = json.loads(fake_answer(prompt))
        if "=== PAGE 2 ===" in prompt.split("TEXT:\n", 1)[1]:
            data["rows"].append(row("Crys-P", "µOECT", "490", "41", "cm2 V-1 s-1", 2, "Crys-P 113 ± 1.38 490 ± 41"))
        return json.dumps(data)

    result = pipeline.run([paper], PROPERTIES, [provider("Fake", with_extra)])
    extra = by_key(result["rows"], "Crys-P", "µOECT")
    assert extra["status"] == "review"
    assert "not one of your target properties" in extra["checks"]
    assert by_key(result["rows"], "Crys-P", "C*")["property_std"] == "volumetric capacitance C*"


def test_areal_capacitance_is_not_accepted_as_volumetric(paper):
    def with_areal(prompt):
        data = json.loads(fake_answer(prompt))
        if "=== PAGE 2 ===" in prompt.split("TEXT:\n", 1)[1]:
            data["rows"].append(row("Crys-P", "C*", "113", "1.38", "μF/cm2", 2, "Crys-P 113 ± 1.38 490 ± 41"))
        return json.dumps(data)

    result = pipeline.run([paper], PROPERTIES, [provider("Fake", with_areal)])
    areal = [r for r in result["rows"] if r["unit"] == "μF/cm2"][0]
    assert areal["status"] == "review"
    assert "doesn't fit this property" in areal["checks"]


# ---------------- smarter waiting ----------------
def test_rate_limit_cooldown_is_short_and_respects_retry_after():
    plain = FakeHttpError(429)
    assert providers.cooldown_for(plain) == providers.RATE_LIMIT_COOLDOWN_SECONDS

    class GoogleStyle(Exception):
        code = 429
    told = GoogleStyle("429 RESOURCE_EXHAUSTED. Please retry in 7s.")
    assert providers.cooldown_for(told) == 7.0

    busy = FakeHttpError(503)
    assert providers.cooldown_for(busy) == providers.BUSY_COOLDOWN_SECONDS


def test_parallel_chunks_spread_across_engines(paper, monkeypatch):
    import threading
    used = {"A": 0, "B": 0}
    lock = threading.Lock()
    papers = []
    for number in range(4):
        item = {}
        item["name"] = "copy" + str(number) + ".pdf"
        # tiny change in the bytes so each copy is a different paper for the cache
        item["bytes"] = paper["bytes"] + (b" " * (number + 1))
        papers.append(item)

    def make(name):
        def call(prompt):
            with lock:
                used[name] = used[name] + 1
            threading.Event().wait(0.3)
            return fake_answer(prompt)
        return call

    pipeline.run(papers, PROPERTIES, [provider("A", make("A")), provider("B", make("B"))], workers=4)
    assert used["A"] >= 1 and used["B"] >= 1


# ---------------- units ----------------
def test_unit_spellings_match():
    assert unit_key("S/cm") == unit_key("S cm-1") == unit_key("S cm⁻¹") == unit_key("S·cm^-1")
    assert unit_key("F cm-1 V-1 s-1") == unit_key("F cm⁻¹ V⁻¹ s⁻¹") == unit_key("F/(cm V s)")


def test_unit_conversion():
    value, error, unit, note = standardize(590.0, 20.0, "S/m")
    assert (value, error, unit) == ("5.9", "0.2", "S/cm")
    assert "converted" in note
    value, error, unit, note = standardize(1.0, None, "furlongs")
    assert unit == "" and "not in standard list" in note


# ---------------- accuracy ----------------
def test_accuracy_report(paper):
    result = pipeline.run([paper], PROPERTIES, [provider("Fake", fake_answer)])
    key = pd.DataFrame([
        {"Material": "PEDOT:Tos", "Property": "μC*", "Value": "72"},
        {"Material": "EG-P (Our result)", "Property": "μC*", "Value": "100"},
        {"Material": "Crys-P", "Property": "μC*", "Value": "490"},
        {"Material": "Crys-P", "Property": "C*", "Value": "113"},
        {"Material": "Crys-P", "Property": "electrical conductivity", "Value": "4100"},
        {"Material": "EG-P", "Property": "electrical conductivity", "Value": "590"},
    ])
    report = evaluate(result["rows"], read_answer_key(key))
    assert report["correct"] == 4          # the hallucinated 520 and made-up Pr-P are wrong
    assert report["wrong"] == 2
    assert report["wrong_caught"] == 2     # verification flagged both wrong rows
    assert report["found"] == 4
    assert len(report["missed"]) == 2      # true 490 and EG-P conductivity were never extracted


# ---------------- highlight ----------------
def test_highlight_finds_table_row(paper):
    png, how = render_evidence(paper["bytes"], 3, "Crys-P\n4100 ± 98", "4100")
    assert png[:4] == b"\x89PNG"
    assert how in ["evidence", "value only"]


def test_highlight_handles_bad_page(paper):
    png, how = render_evidence(paper["bytes"], 99, "anything", "1")
    assert png is None and how == "not found"


# ---------------- excerpts ----------------
def test_excerpt_keeps_the_table_and_drops_unrelated_text():
    from ingest import excerpt
    filler = "Unrelated discussion of device fabrication. " * 200      # about 8,800 characters
    table = "Table 2. Electrical conductivity (S/cm)\nCrys-P\n4100 ± 98\n"
    page = filler + table + filler
    short = excerpt(page, property_words(PROPERTIES))
    assert "4100 ± 98" in short
    assert "Electrical conductivity" in short
    assert len(short) < len(page) / 4


def test_unreadable_single_page_goes_to_another_engine(paper):
    # one engine garbles a page it cant split further -> a different engine gets that page
    def garbles(prompt):
        return "{\"rows\": [{\"material\": \"Crys"

    result = pipeline.run([paper], PROPERTIES, [provider("Garbles", garbles), provider("Good", fake_answer)])
    assert len(result["rows"]) == 6
    assert result["failures"] == []
    assert result["stats"]["calls_by_provider"]["Good"] >= 1


def test_value_with_plus_minus_is_split_and_reference_marks_cited():
    from verify import verify_row
    pages = [{"page": 4, "text": "PEDOT:PSS + EG19\n39 ± 3\n1.9 ± 1.3\n47 ± 6\n"}]
    raw = row("PEDOT:PSS + EG", "μC*", "47 ± 6", "", "F cm-1 V-1 s-1", 4, "PEDOT:PSS + EG19 39 ± 3 1.9 ± 1.3 47 ± 6")
    raw["reference"] = "19"
    result = verify_row(raw, pages, "inal.pdf", PROPERTIES)
    assert result["value"] == "47" and result["error"] == "6"
    assert result["status"] == "verified"
    assert result["origin"] == "cited" and result["reference"] == "19"
    assert "reference [19]" in result["checks"]


def test_real_inal_rows_now_match_the_answer_key():
    # rows exactly as the ai returned them in the real run on the Inal paper
    from verify import verify_row
    real = [
        ("PEDOT:TOS [VPP]33", "C*", "136 ± 50"), ("PEDOT:TOS [VPP]33", "μC*", "72 ± 14"),
        ("PEDOT:PSS + EG19", "C*", "39 ± 3"), ("PEDOT:PSS + EG19", "μC*", "47 ± 6"),
        ("PEDOT:PSTFSILi10024", "C*", "26 ± 10"), ("PEDOT:PSTFSILi10024", "μC*", "20 ± 1.6"),
        ("PEDOT:DS + EG34", "C*", "65 ± 46"), ("PEDOT:DS + EG34", "μC*", "2.2 ± 0.9"),
        ("PEDOT:PMATFSILi8024", "C*", "27 ± 7"), ("PEDOT:PMATFSILi8024", "μC*", "0.15 ± 0.01"),
    ]
    page_text = ""
    rows = []
    for material, prop, value in real:
        evidence = material + " " + value
        page_text = page_text + evidence + "\n"
    pages = [{"page": 4, "text": page_text}]
    for material, prop, value in real:
        raw = row(material, prop, value, "", "F cm-3" if prop == "C*" else "F cm-1 V-1 s-1", 4, material + " " + value)
        rows.append(verify_row(raw, pages, "inal.pdf", PROPERTIES))
    key = pd.read_csv(os.path.join(os.path.dirname(HERE), "answer_key_inal.csv"))
    report = evaluate(rows, read_answer_key(key))
    assert report["found"] == 10
    assert all(r["status"] == "verified" for r in rows)


# ---------------- tables (built like the real Inal 2017 Table 1) ----------------
INAL_PAGE = (
    "Table 1 Summary of material properties\n"
    "Material\nC* (F cm−3)\nµOECT (cm2 V−1 s−1)\nµC* (F cm−1 V−1 s−1)\n[µC*]OECT (F cm−1 V−1 s−1)\n"
    "PEDOT:PSS + EG19\n39 ± 3\n1.9 ± 1.3\n75 ± 51\n47 ± 6\n"
    "PEDOT:TOS [VPP]33\n136 ± 50\n0.93 ± 0.72\n126 ± 108\n72 ± 14\n"
    "p(g2T‑TT)32\n241 ± 94\n0.94 ± 0.25\n227 ± 107\n261 ± 29\n"
    "p(g2T‑T)22\n220 ± 30\n0.28 ± 0.1\n62 ± 24\n167 ± 65\n"
)


def inal_row(material, prop, value, error, evidence, unit="F cm−1 V−1 s−1"):
    item = row(material, prop, value, error, unit, 4, evidence)
    item["reference"] = ""
    return item


INAL_MATERIALS = ["PEDOT:PSS + EG", "PEDOT:TOS", "p(g2T-TT)", "p(g2T-T)"]


def test_table_values_with_cells_in_between_are_verified():
    from verify import verify_row
    pages = [{"page": 4, "text": INAL_PAGE}]
    # evidence exactly the way the ai wrote it in the real run: it skips the cells in between
    cases = [
        inal_row("PEDOT:PSS + EG", "[µC*]OECT", "47", "6", "PEDOT:PSS + EG 47 ± 6"),
        inal_row("PEDOT:PSS + EG", "µC*", "75", "51", "PEDOT:PSS + EG 75 ± 51"),
        inal_row("PEDOT:TOS", "[µC*]OECT", "72", "14", "PEDOT:TOS 72 ± 14"),
        inal_row("p(g2T-TT)", "[µC*]OECT", "261", "29", "p(g2T-TT) 261 ± 29"),
        inal_row("p(g2T-T)", "µC*", "62", "24", "p(g2T-T) 62 ± 24"),
    ]
    for raw in cases:
        result = verify_row(raw, pages, "inal.pdf", PROPERTIES, INAL_MATERIALS)
        assert result["status"] == "verified", (raw["material"], raw["value"], result["checks"])
        assert "matched as a table row" in result["checks"]


def test_table_value_credited_to_the_wrong_material_is_flagged():
    from verify import verify_row
    pages = [{"page": 4, "text": INAL_PAGE}]
    # 261 ± 29 belongs to p(g2T-TT), not p(g2T-T) - similar names, different polymers
    wrong = inal_row("p(g2T-T)", "[µC*]OECT", "261", "29", "p(g2T-T) 261 ± 29")
    result = verify_row(wrong, pages, "inal.pdf", PROPERTIES, INAL_MATERIALS)
    assert result["status"] == "flagged"
    # 72 ± 14 is PEDOT:TOS, the row above is PEDOT:PSS + EG
    wrong = inal_row("PEDOT:PSS + EG", "[µC*]OECT", "72", "14", "PEDOT:PSS + EG 72 ± 14")
    result = verify_row(wrong, pages, "inal.pdf", PROPERTIES, INAL_MATERIALS)
    assert result["status"] == "flagged"
    # a value that is nowhere in the table
    wrong = inal_row("PEDOT:TOS", "[µC*]OECT", "80", "14", "PEDOT:TOS 80 ± 14")
    result = verify_row(wrong, pages, "inal.pdf", PROPERTIES, INAL_MATERIALS)
    assert result["status"] == "flagged"


def test_scorer_does_not_confuse_similar_polymer_names():
    from evaluate import same_material
    assert same_material("PEDOT:TOS", "PEDOT:TOS [VPP]")
    assert same_material("PEDOT:PSS + EG19", "PEDOT:PSS + EG")
    assert not same_material("p(g2T-TT)", "p(g2T-T)")
    assert not same_material("PEDOT:PSS", "PEDOT:PSS + EG")


# ---------------- live stages for the ui ----------------
def test_stages_are_reported_in_order_from_real_events(paper):
    seen = []
    pipeline.run([paper], PROPERTIES, [provider("Fake", fake_answer)], on_stage=lambda name, detail: seen.append(name))
    order = []
    for name in seen:
        if name not in order:
            order.append(name)
    assert order == pipeline.STAGES
    # the second run is served from cache: stages still run in order, extract says it reused
    details = []
    pipeline.run([paper], PROPERTIES, [provider("Fake", fake_answer)], on_stage=lambda name, detail: details.append((name, detail)))
    assert ("extract", "Reusing earlier results") in details


# ---------------- threads (saved to disk) ----------------
def test_thread_lifecycle(tmp_path, monkeypatch):
    import threads
    monkeypatch.setattr(threads, "THREADS_DIR", str(tmp_path / "threads"))
    t = threads.new_thread()
    assert t["title"] == "New thread"
    threads.add_paper(t, "Inal_2017.pdf", b"%PDF-1")
    threads.add_paper(t, "PNAS_2016.pdf", b"%PDF-2")
    assert t["title"] == "Inal_2017 + 1 more"          # default name = the file names
    threads.remove_paper(t, "PNAS_2016.pdf")
    assert t["title"] == "Inal_2017"
    threads.rename(t, "OECT benchmark")
    threads.add_paper(t, "Extra.pdf", b"%PDF-3")
    assert t["title"] == "OECT benchmark"              # a chosen name is never overwritten
    t["properties"] = "μC*"
    threads.save(t)
    again = threads.load(t["id"])                        # survives a reload
    assert again["title"] == "OECT benchmark" and again["properties"] == "μC*"
    assert sorted(threads.paper_bytes(again).keys()) == ["Extra.pdf", "Inal_2017.pdf"]
    threads.delete(t["id"])
    assert threads.load(t["id"]) is None
    assert threads.list_threads() == []


def test_spaces_keep_visitors_apart(tmp_path, monkeypatch):
    # on a public deploy every browser has its own space; one visitor never sees another's papers
    import threads
    monkeypatch.setattr(threads, "THREADS_DIR", str(tmp_path / "threads"))
    alice, bob = threads.new_space_id(), threads.new_space_id()
    a = threads.new_thread(alice)
    threads.add_paper(a, "Inal_2017.pdf", b"%PDF-1")
    threads.save(a)
    assert [t["id"] for t in threads.list_threads(alice)] == [a["id"]]
    assert threads.list_threads(bob) == []
    assert threads.load(a["id"], bob) is None            # knowing the thread id isn't enough
    threads.delete(a["id"], bob)                         # bob can't delete it either
    assert threads.load(a["id"], alice) is not None
    assert threads.list_threads("") == []                # the shared local list doesn't show space folders
    assert threads.clean_space("../../etc") == ""        # junk in the url can't escape the folder
    assert threads.load("../" + alice, "") is None


# ---------------- suggested properties ----------------
def test_suggestions_keep_only_names_in_the_paper(paper):
    import suggest
    def fake_suggest(prompt):
        assert "Supplementary Table 2" in prompt          # the skim includes the tables
        return json.dumps({"rows": [
            {"property": "electrical conductivity", "unit": "S/cm"},
            {"property": "Volumetric capacitance", "unit": "F cm-3"},
            {"property": "hole mobility", "unit": "cm2/Vs"},      # not in the paper -> dropped
            {"property": "", "unit": ""},
        ]})
    found = suggest.suggest({"a.pdf": paper["bytes"], "b.pdf": paper["bytes"]}, [provider("Fake", fake_suggest)])
    names = [item["name"] for item in found["items"]]
    assert names == ["electrical conductivity", "Volumetric capacitance"]
    assert found["items"][0]["papers"] == ["a.pdf", "b.pdf"]     # merged across papers
    assert found["failures"] == []


def test_suggestion_chips_edit_the_properties_box():
    import suggest
    names = ["μC*", "electrical conductivity"]
    text = suggest.apply_selection("mobility", names, ["μC*"])
    assert text == "mobility, μC*"                              # typed text stays, chip added
    assert suggest.selected_in(text, names) == ["μC*"]
    text = suggest.apply_selection(text, names, ["electrical conductivity"])
    assert text == "mobility, electrical conductivity"         # turned-off chip removed
    assert suggest.apply_selection("", names, []) == ""


# ---------------- scientific notation ----------------
def test_scientific_notation_is_one_number():
    from text_tools import numbers_in, to_number, same_number
    for written in ["6.61 x 10-4", "6.61 × 10⁻⁴", "6.61x10^-4", "6.61e-4", "0.000661", "6.61 * 10^(-4)"]:
        assert to_number(written) is not None and same_number(to_number(written), 0.000661), written
    assert numbers_in("136 ± 50") == [136.0, 50.0]          # ordinary values unchanged
    assert not same_number(1e-12, 2e-12)                     # tiny numbers are still told apart


def test_scientific_value_verifies_against_the_pdf_text():
    from verify import verify_row
    # the garnet paper prints "6.61 x 10-4 S/cm"; an ai that writes 6.61e-4 is RIGHT, not hallucinating
    pages = [{"page": 1, "text": "The maximum conductivity of 6.61 x 10-4 S/cm is obtained for 0.25 Ta ceramic."},
             {"page": 2, "text": "Table 3\nContent of Ta (y)\nIonic Conductivity (S/cm)\n0.15\n3.50 x 10-5\n0.39"}]
    sentence = row("0.25 Ta", "ionic conductivity", "6.61e-4", "", "S/cm", 1,
                   "The maximum conductivity of 6.61 x 10-4 S/cm is obtained for 0.25 Ta ceramic")
    table = row("y = 0.15", "ionic conductivity", "3.50 x 10-5", "", "S/cm", 2, "0.15 3.50 x 10-5 0.39")
    for raw in [sentence, table]:
        assert verify_row(raw, pages, "garnet.pdf", "ionic conductivity")["status"] == "verified"
