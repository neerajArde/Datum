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
