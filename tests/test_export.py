import json

import pytest

from bookkeywordlab.clustering import cluster_terms
from bookkeywordlab.export import ExportError, render
from bookkeywordlab.planner import build_plan
from bookkeywordlab.scoring import score_candidates


@pytest.fixture()
def sample_plan(default_rules):
    terms = [
        "ai for beginners",
        "plain english guide to agents",
        "local ai basics",
        "chatgpt prompt secrets",
        "automation wins for work",
    ]
    scored = score_candidates(terms, default_rules)
    clusters = cluster_terms(scored, default_rules)
    return build_plan(scored, clusters, default_rules, book_title="The Massive AI Manual")


def test_text_export_is_truthy_and_complete(sample_plan):
    text = render(sample_plan, "text")
    assert "BOOK KEYWORD LAB" in text
    assert "SEVEN KEYWORD SLOTS" in text
    assert "The Massive AI Manual" in text
    assert "ai for beginners" in text
    assert "CATEGORY SHORTLIST" in text
    assert "chatgpt prompt secrets" in text  # skipped candidates show up with reasoning
    assert "REASONING NOTES" in text


def test_text_export_lines_fit_copyslot(sample_plan):
    text = render(sample_plan, "text")
    for line in text.splitlines():
        if line.startswith(("  1.", "  2.", "  3.", "  4.", "  5.", "  6.", "  7.")):
            phrase = line.split(". ", 1)[1]
            if not phrase.startswith("("):
                assert len(phrase) <= 50


def test_markdown_export(sample_plan):
    md = render(sample_plan, "markdown")
    assert md.startswith("# Book Keyword Lab export")
    assert "- **Computers & Technology > Computer Science > Artificial Intelligence**" in md
    assert "`ai for beginners`" in md


def test_json_export_roundtrips(sample_plan):
    data = json.loads(render(sample_plan, "json"))
    assert data["book_title"] == "The Massive AI Manual"
    assert len(data["slots"]) == 7
    assert data["slots"][0]["phrase"] == "ai for beginners"
    assert any(c["kind"] == "primary" for c in data["categories"])


def test_unknown_format_raises(sample_plan):
    with pytest.raises(ExportError):
        render(sample_plan, "spreadsheet")
