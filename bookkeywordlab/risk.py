"""Flag wording that could get keywords rejected or keep us out of trouble."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .rules import Rules

SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


@dataclass
class RiskFlag:
    rule_id: str
    severity: str
    matched: str
    reason: str

    @property
    def rank(self) -> int:
        return SEVERITY_RANK.get(self.severity, 3)


def assess_risk(term: str, rules: Rules) -> List[RiskFlag]:
    """Return every risk rule that matches (one flag per rule, sorted most-serious first)."""
    text = (term or "").strip()
    flags: List[RiskFlag] = []
    for rule in rules.risk_rules:
        hit = rule.pattern.search(text)
        if hit:
            flags.append(
                RiskFlag(rule_id=rule.id, severity=rule.severity, matched=hit, reason=rule.reason)
            )
    flags.sort(key=lambda f: (f.rank, f.rule_id))
    return flags


def worst_severity(flags: List[RiskFlag]) -> str:
    if not flags:
        return ""
    return sorted(flags, key=lambda f: f.rank)[0].severity


def high_risk_flags(flags: List[RiskFlag]) -> List[RiskFlag]:
    return [f for f in flags if f.severity == "high"]


def badge(flags: List[RiskFlag]) -> str:
    """Short inline marker for tables: '!' = high risk, '?' = medium."""
    sev = worst_severity(flags)
    if sev == "high":
        return "!"
    if sev in ("medium", "low"):
        return "?"
    return ""
