import json

import pytest

from bookkeywordlab.storage import DEFAULT_STATE_FILENAME, State, StorageError


def test_add_terms_dedupes_case_and_spacing(tmp_path):
    state = State.load(str(tmp_path / "state.json"))
    added, present = state.add_terms(["AI for  Beginners", "ai for beginners", "local ai"], "manual")
    assert added == ["AI for  Beginners", "local ai"]
    assert present == ["ai for beginners"]
    state.save()

    reloaded = State.load(str(tmp_path / "state.json"))
    assert sorted(t.lower() for t in reloaded.terms()) == sorted(
        ["ai for  beginners", "local ai"]
    )


def test_add_terms_records_sources(tmp_path):
    state = State.load(str(tmp_path / "state.json"))
    state.add_terms(["prompt writing"], "manual")
    state.add_terms(["Prompt Writing"], "brainstorm:llama3.2")
    entry = state.candidates["prompt writing"]
    assert entry["sources"] == ["manual", "brainstorm:llama3.2"]


def test_remove_terms_exact_then_forgiving(tmp_path):
    state = State.load(str(tmp_path / "state.json"))
    state.add_terms(["AI for Beginners", "Landed Estate"], "manual")
    removed, missing = state.remove_terms(["ai for beginners"])
    assert removed == ["AI for Beginners"]
    removed2, missing2 = state.remove_terms(["landed estate"])
    assert removed2 == ["Landed Estate"] and missing2 == []
    removed3, missing3 = state.remove_terms(["landed estate"])
    assert removed3 == [] and missing3 == ["landed estate"]


def test_roundtrip_keeps_book_title(tmp_path):
    path = str(tmp_path / "state.json")
    state = State.load(path)
    state.set_title("The Massive AI Manual")
    state.add_terms(["term one", "term two"], "manual")
    state.save()
    loaded = State.load(path)
    assert loaded.book_title == "The Massive AI Manual"
    assert len(loaded.terms()) == 2


def test_corrupt_state_raises_friendly_error(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{ not json at all ", "utf-8")
    with pytest.raises(StorageError) as err:
        State.load(str(path))
    assert "could not read state file" in str(err.value)


def test_future_version_raises(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"version": 99, "candidates": {}}), "utf-8")
    with pytest.raises(StorageError):
        State.load(str(path))


def test_default_state_path_points_here():
    import os

    assert DEFAULT_STATE_FILENAME == "book-keyword-lab-state.json"
    path = __import__("bookkeywordlab.storage", fromlist=["default_state_path"]).default_state_path()
    assert os.path.basename(path) == DEFAULT_STATE_FILENAME
    assert os.path.dirname(path) == os.getcwd()
