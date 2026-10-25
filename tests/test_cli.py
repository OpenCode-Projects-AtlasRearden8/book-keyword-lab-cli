import io
import json

import pytest

from bookkeywordlab.cli import main


@pytest.fixture()
def state_path(tmp_path):
    return str(tmp_path / "state.json")


def run(capsys, *argv):
    code = main(list(argv))
    out = capsys.readouterr().out
    return code, out


def test_init_uses_existing_identity_state(tmp_path, capsys, state_path):
    code, out = run(capsys, "init", "-t", "The Massive AI Manual", "--state", state_path)
    assert code == 0
    assert "The Massive AI Manual" in out
    data = json.load(open(state_path, encoding="utf-8"))
    assert data["book_title"] == "The Massive AI Manual"


def test_full_flow_without_network(tmp_path, capsys, state_path, default_rules):
    run(capsys, "init", "-t", "The Massive AI Manual", "--state", state_path)
    code, out = run(
        capsys, "add", "--state", state_path,
        "ai for beginners", "plain english guide to agents",
        "guaranteed bestseller", "chatgpts prompt secrets",
    )
    assert code == 0
    assert "+ ai for beginners" in out

    code, out = run(capsys, "list", "--state", state_path)
    assert code == 0 and "candidate(s)" in out and "!" in out  # risk badge present

    code, out = run(capsys, "score", "--state", state_path)
    assert code == 0
    assert "plain english guide to agents" in out
    assert "+" in out  # explained boosts

    code, out = run(capsys, "cluster", "--state", state_path)
    assert code == 0 and "cluster(s)" in out

    code, out = run(capsys, "risk", "--state", state_path)
    assert code == 0
    assert "overpromise" in out and "brand-name" in out

    code, out = run(capsys, "plan", "--state", state_path)
    assert code == 0
    assert "SEVEN KEYWORD SLOTS" in out
    assert "  1. " in out
    assert "chatgpts prompt secrets" in out  # skipped, not slotted
    assert "CATEGORY SHORTLIST" in out

    out_file = str(tmp_path / "kw.md")
    code, out = run(capsys, "export", "-f", "markdown", "-o", out_file, "--state", state_path)
    assert code == 0 and "wrote" in out
    md = open(out_file, encoding="utf-8").read()
    assert "## Seven keyword slots" in md

    json_file = str(tmp_path / "kw.json")
    run(capsys, "export", "-f", "json", "-o", json_file, "--state", state_path)
    data = json.load(open(json_file, encoding="utf-8"))
    assert len(data["slots"]) == 7


def test_add_via_pasted_stdin(tmp_path, capsys, state_path, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("- local ai basics\n2. privacy basics\n"))
    code, out = run(capsys, "add", "--state", state_path, "-")
    assert code == 0
    assert "+ local ai basics" in out and "+ privacy basics" in out


def test_remove_nomatch_reports(tmp_path, capsys, state_path):
    run(capsys, "add", "--state", state_path, "term keep")
    code, out = run(capsys, "remove", "nope nothing", "--state", state_path)
    assert code == 0 and "not found" in out
    code, out = run(capsys, "remove", "term keep", "--state", state_path)
    assert code == 0 and "- term keep" in out


def test_score_empty_state_is_friendly(tmp_path, capsys, state_path):
    code, out = run(capsys, "score", "--state", state_path)
    assert code == 1 and "no candidates yet" in out
    code, out = run(capsys, "plan", "--state", state_path)
    assert code == 1


def test_missing_rules_file_reports_error(tmp_path, capsys, state_path):
    run(capsys, "add", "--state", state_path, "term one")
    code, out = run(capsys, "score", "--state", state_path, "--rules", str(tmp_path / "nope.yaml"))
    assert code == 1 and "error:" in out


def test_reset_requires_yes_when_noninteractive(tmp_path, capsys, state_path):
    run(capsys, "add", "--state", state_path, "term")
    code, out = run(capsys, "reset", "--state", state_path)
    assert code == 1 and "--yes" in out
    code, out = run(capsys, "reset", "--yes", "--state", state_path)
    assert code == 0 and "deleted" in out
    import os

    assert not os.path.exists(state_path)


def test_brainstorm_via_fake_endpoint(tmp_path, capsys, state_path, endpoint_factory):
    handle = endpoint_factory(
        content=["ai for beginners", "brand free idea", "guaranteed bestseller"]
    )
    run(capsys, "init", "--state", state_path)
    code, out = run(
        capsys, "brainstorm", "--state", state_path,
        "--base-url", handle.base_url, "--model", "test-model",
        "beginner-friendly AI manual",
    )
    assert code == 0
    assert "guaranteed bestseller" in out  # shown, with its risk marker
    assert "!" in out
    state = json.load(open(state_path, encoding="utf-8"))
    keys = " ".join(state["candidates"].keys())
    assert "brand free idea" in keys  # brainstorm results were added
    assert "guaranteed bestseller" in keys


def test_brainstorm_no_add(tmp_path, capsys, state_path, endpoint_factory):
    handle = endpoint_factory(content=["fresh idea only"])
    run(capsys, "init", "--state", state_path)
    code, out = run(
        capsys, "brainstorm", "--state", state_path, "--no-add",
        "--base-url", handle.base_url, "--model", "test-model",
    )
    assert code == 0 and "not added" in out
    state = json.load(open(state_path, encoding="utf-8"))
    assert state["candidates"] == {}


def test_brainstorm_unreachable_endpoint(tmp_path, capsys, state_path):
    run(capsys, "init", "--state", state_path)
    code, out = run(
        capsys, "brainstorm", "--state", state_path,
        "--base-url", "http://127.0.0.1:1/v1", "--timeout", "1",
    )
    assert code == 1 and "brainstorm unavailable" in out and "ollama" in out.lower()


def test_models_command(endpoint_factory, capsys, state_path):
    handle = endpoint_factory(model_ids=["llama3.2", "mistral"])
    code, out = run(capsys, "models", "--base-url", handle.base_url)
    assert code == 0
    assert "llama3.2" in out and "mistral" in out


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as err:
        main(["--version"])
    assert "bkwl" in capsys.readouterr().out
