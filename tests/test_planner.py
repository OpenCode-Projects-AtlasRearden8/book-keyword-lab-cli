import pytest

from bookkeywordlab.clustering import cluster_terms
from bookkeywordlab.planner import build_plan, plan_to_dict
from bookkeywordlab.rules import parse_rules
from bookkeywordlab.scoring import score_candidates


@pytest.fixture()
def tiny_rules():
    data = {
        "profile": {"name": "Tiny"},
        "scoring": {
            "base": 50,
            "length": {"min_chars": 3, "sweet_min_words": 2, "sweet_max_words": 6},
            "boosts": [
                {"pattern": "guide", "weight": 4, "reason": "guide boost"},
                {"pattern": "beginners", "weight": 4, "reason": "beginners boost"},
            ],
            "penalties": [{"pattern": "hype", "weight": -9, "reason": "hype"}],
        },
        "risk": {
            "rules": [
                {"id": "brand", "severity": "high", "pattern": "zappo\\w*", "regex": True, "reason": "brand"},
                {"id": "spam", "severity": "medium", "pattern": "hype", "reason": "spam"},
            ]
        },
        "planner": {"slots": 7, "slot_chars": 50, "primary_categories": 2, "alternate_categories": 1},
        "categories": [
            {"name": "Shelves > AI", "fit_terms": ["ai", "beginners"], "weight": 1.0, "note": "n1"},
            {"name": "Shelves > Writing", "fit_terms": ["guide", "beginners"], "weight": 1.0, "note": "n2"},
            {"name": "Shelves > Cooking", "fit_terms": ["recipes", "kitchen"], "weight": 0.9, "note": "n3"},
        ],
    }
    return parse_rules(data, "tiny")


def test_plan_fills_seven_slots_and_sorts_desc(tiny_rules):
    terms = [
        "beginners guide to zapps",
        "plain guide",
        "beginners start here",
        "quiet guide",
        "lonely term",
        "one more fill",
        "and another",
        "eighth keeps out",
    ]
    scored = score_candidates(terms, tiny_rules)
    clusters = cluster_terms(scored, tiny_rules)
    plan = build_plan(scored, clusters, tiny_rules, book_title="T")
    assert len(plan.slots) == 7
    filled = [s for s in plan.slots if s.phrase is not None]
    assert len(filled) == 7
    scores = [s.score for s in filled]
    assert scores == sorted(scores, reverse=True)
    phrases = [s.phrase for s in filled]
    assert len(set(p.lower() for p in phrases)) == 7
    assert all(len(p) <= 50 for p in phrases)
    # the low-scoring cluster member ('quiet guide') stays behind its cluster rep
    assert "quiet guide" not in phrases


def test_plan_leaves_open_slots_with_a_note(tiny_rules):
    scored = score_candidates(["beginners guide", "lonely term"], tiny_rules)
    clusters = cluster_terms(scored, tiny_rules)
    plan = build_plan(scored, clusters, tiny_rules, book_title="T")
    assert len(plan.slots) == 7
    opened = [s for s in plan.slots if s.phrase is None]
    assert len(opened) == 5
    assert all(any("open" in n for n in s.notes) for s in opened)


def test_high_risk_terms_are_skipped_from_slots(tiny_rules):
    scored = score_candidates(["zappo machine hype", "beginners guide"], tiny_rules)
    clusters = cluster_terms(scored, tiny_rules)
    plan = build_plan(scored, clusters, tiny_rules, book_title="T")
    phrases = [s.phrase for s in plan.slots if s.phrase]
    assert "zappo machine hype" not in phrases
    skipped_terms = [t for t, _ in plan.skipped]
    assert "zappo machine hype" in skipped_terms
    assert any("high-risk 'brand'" in r for t, r in plan.skipped)


def test_overlong_terms_are_skipped(tiny_rules):
    long_term = "x" * 60
    scored = score_candidates([long_term, "beginners guide"], tiny_rules)
    clusters = cluster_terms(scored, tiny_rules)
    plan = build_plan(scored, clusters, tiny_rules)
    assert [s.phrase for s in plan.slots if s.phrase] == ["beginners guide"]
    assert any("slot limit" in r for t, r in plan.skipped if t == long_term)


def test_medium_risk_terms_warn_but_may_sit_in_slots(tiny_rules):
    scored = score_candidates(["beginners guide"], tiny_rules)
    clusters = cluster_terms(scored, tiny_rules)
    plan = build_plan(scored, clusters, tiny_rules)
    slot = plan.slots[0]
    assert slot.phrase == "beginners guide"


def test_categories_shortlist_with_primary_and_alternates(tiny_rules):
    scored = score_candidates(["beginners guide to zapps", "quiet guide"], tiny_rules)
    plan = build_plan(scored, [], tiny_rules)
    kinds = [c.kind for c in plan.categories]
    assert kinds.count("primary") == 2
    assert kinds.count("alternate") == 1
    top = plan.categories[0]
    assert top.name == "Shelves > Writing"  # both candidates carry 'guide'/'beginners'
    assert "beginners guide to zapps" in " ".join(top.matched)
    second = plan.categories[1]
    assert second.name == "Shelves > AI"


def test_plan_to_dict_roundtrip_shape(tiny_rules):
    scored = score_candidates(["beginners guide"], tiny_rules)
    plan = build_plan(scored, [], tiny_rules, book_title="T")
    data = plan_to_dict(plan)
    assert data["book_title"] == "T"
    assert len(data["slots"]) == 7
    assert data["slots"][0]["phrase"] == "beginners guide"
    assert set(data["slots"][0]) == {
        "slot", "phrase", "score", "cluster", "new_words", "repeated_words", "notes", "risks"
    }


def test_default_rules_plan_smoke(default_rules):
    terms = [
        "ai for beginners",
        "plain english guide to agents",
        "local ai basics",
        "chatgpt prompt secrets",
        "guaranteed bestseller",
        "automation wins for work",
    ]
    from bookkeywordlab.risk import assess_risk

    scored = score_candidates(terms, default_rules)
    assert all("chatgpt" not in s.term or any(
        f.rule_id == "brand-name" for f in assess_risk(s.term, default_rules)) for s in scored)
