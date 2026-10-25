import pytest

from bookkeywordlab.scoring import score_candidates, score_term
from bookkeywordlab.textutil import tokenize


def test_beginner_phrase_beats_plain_topic(default_rules):
    beginner = score_term("ai for beginners", default_rules)
    plain = score_term("ai", default_rules)
    assert beginner.score > plain.score
    notes = " ".join(beginner.notes)
    assert "for beginners" in notes


def test_bare_ai_word_boundary_matters(default_rules):
    chair = score_term("chair as a hobby", default_rules)
    assert not any("'ai'" in n for n in chair.notes)


def test_notes_explain_bumps_and_hits(default_rules):
    result = score_term("plain english guide to agents", default_rules)
    joined = "\n".join(result.notes)
    assert "+6" in joined and "plain english" in joined
    assert "sweet spot" in joined


def test_vague_words_are_penalized(default_rules):
    vague = score_term("ai stuff for things", default_rules)
    clean = score_term("ai walkthrough", default_rules)
    assert vague.score < clean.score
    assert any("-4" in n for n in vague.notes)


def test_too_long_for_a_slot_is_penalized(default_rules):
    long_term = " ".join(["keyword"] * 20)
    result = score_term(long_term, default_rules)
    assert any("50-character" in n for n in result.notes)


def test_single_word_penalized(default_rules):
    result = score_term("automation", default_rules)
    assert any("1 word" in n for n in result.notes)


def test_scores_clamp_to_the_100_ceiling():
    from bookkeywordlab.rules import parse_rules

    rules = parse_rules(
        {
            "scoring": {
                "base": 50,
                "boosts": [
                    {"pattern": "great", "weight": 30},
                    {"pattern": "easy", "weight": 30},
                ],
            }
        },
        "inline",
    )
    assert score_term("great and easy walkthroughs", rules).score == 100


def test_scores_never_go_negative(default_rules):
    rough = "stuff things misc etc best ultimate insane amazing secret pdf your own"
    result = score_term(rough, default_rules)
    assert 0 <= result.score <= 5


def test_tokens_exclude_stopwords(default_rules):
    result = score_term("ai for beginners", default_rules)
    assert set(tokenize("ai for beginners")) - default_rules.stopwords == set(result.tokens)


def test_sort_is_stable_and_deterministic(default_rules):
    terms = ["ai for beginners", "automation", "local ai basics", "ai walkthrough"]
    first = [(s.term, s.score) for s in score_candidates(terms, default_rules)]
    second = [(s.term, s.score) for s in score_candidates(terms, default_rules)]
    assert first == second
    assert first[0][1] >= first[-1][1]
