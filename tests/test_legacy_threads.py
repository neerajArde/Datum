# tests/test_legacy_threads.py
# Tests for the v1 Streamlit app's saved threads (threads.py). They stay next to the v1 app,
# which keeps running until the new Next.js frontend replaces it.
# run from the repo root with:  python -m pytest -q

import threads


def test_thread_lifecycle(tmp_path, monkeypatch):
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
