import pytest

from bookkeywordlab.risk import assess_risk, badge, high_risk_flags, worst_severity


def test_brand_names_flag_high(default_rules):
    flags = assess_risk("chatgpt prompt pack", default_rules)
    assert any(f.rule_id == "brand-name" and f.severity == "high" for f in flags)
    assert assess_risk("kindle ebooks", default_rules)  # brand family
    assert assess_risk("amazon kdp guide", default_rules)


def test_plural_brands_still_flag(default_rules):
    flags = assess_risk("chatgpts prompt secrets", default_rules)
    assert any(f.rule_id == "brand-name" for f in flags)


def test_claims_flag_high(default_rules):
    flags = assess_risk("guaranteed bestseller", default_rules)
    assert any(f.rule_id == "overpromise" for f in flags)
    assert worst_severity(flags) == "high"


def test_personal_data_flags(default_rules):
    assert any(
        f.rule_id == "privacy-or-secrets" for f in assess_risk("contact me at me@example.com", default_rules)
    )
    assert any(
        f.rule_id == "privacy-or-secrets" for f in assess_risk("enter your password", default_rules)
    )


def test_spammy_is_medium_only(default_rules):
    flags = assess_risk("cheap simple pendant lights", default_rules)
    assert flags
    assert worst_severity(flags) in ("medium", "low")
    assert not high_risk_flags(flags)


def test_clean_terms_pass(default_rules):
    assert assess_risk("ai for beginners", default_rules) == []
    assert assess_risk("local ai walkthrough", default_rules) == []
    assert assess_risk("prompt writing basics", default_rules) == []


def test_badge_marker(default_rules):
    assert badge(assess_risk("chatgpt prompts", default_rules)) == "!"
    assert badge(assess_risk("cheap click here stuff", default_rules)) == "?"
    assert badge([]) == ""
