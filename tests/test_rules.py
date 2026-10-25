import pytest

from bookkeywordlab.rules import RulesError, load_rules, parse_rules
from bookkeywordlab.scoring import score_term


def test_default_rules_load_and_have_buckets(default_rules):
    assert default_rules.base_score == 50
    assert default_rules.slot_count == 7
    assert default_rules.slot_chars == 50
    assert any(b.weight for b in default_rules.boosts)
    assert any(r.id == "brand-name" for r in default_rules.risk_rules)
    assert any("artificial intelligence" in c["name"].lower() for c in default_rules.categories)
    assert default_rules.profile.get("name")


def test_regex_flag_is_respected(tmp_path):
    path = tmp_path / "rules.yaml"
    path.write_text(
        "profile:\n"
        "scoring:\n"
        "  base: 50\n"
        "  boosts:\n"
        "    - pattern: 'a.c'\n"
        "      weight: 5\n"
        "      regex: true\n"
        "      reason: regex works\n",
        "utf-8",
    )
    rules = load_rules(str(path))
    scored = score_term("zabc zy", rules)  # regex 'a.c' matches 'abc'
    assert rules.boosts[0].pattern.search("zabc zy") == "abc"
    assert scored.score > rules.base_score

    # a plain pattern must be treated literally, not as a regex
    path.write_text(
        "profile:\n"
        "scoring:\n"
        "  base: 50\n"
        "  boosts:\n"
        "    - pattern: 'a.c'\n"
        "      weight: 5\n",
        "utf-8",
    )
    rules2 = load_rules(str(path))
    assert rules2.boosts[0].pattern.search("zabc zy") is None
    assert score_term("zabc zy", rules2).score == rules2.base_score + 5  # just the word-count bump


def test_missing_rules_file_raises():
    with pytest.raises(RulesError):
        load_rules("/nonexistent/rules.yaml")


def test_invalid_yaml_raises(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("scoring: [this, is, not, a, mapping\n", "utf-8")
    with pytest.raises(RulesError):
        load_rules(str(path))


def test_non_mapping_rules_raises(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("- just\n- a\n- list\n", "utf-8")
    with pytest.raises(RulesError):
        load_rules(str(path))


def test_parse_rules_minimum():
    rules = parse_rules({}, "inline")
    assert rules.slot_count == 7  # planner default
    assert rules.base_score == 50
    assert rules.categories == []
