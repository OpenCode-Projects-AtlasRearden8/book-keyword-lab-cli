"""Loading and validation of the local rules file (YAML heuristics)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib import resources
from typing import Any, Dict, List, Optional, Union

import yaml


class RulesError(Exception):
    """Raised when a rules file cannot be read or parsed."""


class _Pattern:
    """Case-insensitive matcher; literal text by default, regex when asked."""

    def __init__(self, spec: Union[str, Dict[str, Any]]):
        if isinstance(spec, str):
            pattern, regex = spec, False
        else:
            if not isinstance(spec, dict) or "pattern" not in spec:
                raise RulesError(f"invalid pattern spec: {spec!r}")
            pattern = str(spec["pattern"])
            regex = bool(spec.get("regex", False))
        try:
            self.regex = re.compile(pattern if regex else re.escape(pattern), re.IGNORECASE)
        except re.error as exc:  # pragma: no cover - defensive
            raise RulesError(f"invalid pattern {pattern!r}: {exc}") from exc
        self.source = pattern

    def search(self, text: str) -> Optional[str]:
        m = self.regex.search(text)
        return m.group(0) if m else None


@dataclass
class WeightedMatch:
    pattern: _Pattern
    weight: int
    reason: str


@dataclass
class RiskRule:
    id: str
    severity: str
    pattern: _Pattern
    reason: str


@dataclass
class Rules:
    raw: Dict[str, Any]
    source: str
    profile: Dict[str, Any] = field(default_factory=dict)
    stopwords: set = field(default_factory=set)
    base_score: int = 50
    boosts: List[WeightedMatch] = field(default_factory=list)
    penalties: List[WeightedMatch] = field(default_factory=list)
    length: Dict[str, Any] = field(default_factory=dict)
    risk_rules: List[RiskRule] = field(default_factory=list)
    categories: List[Dict[str, Any]] = field(default_factory=list)
    clustering: Dict[str, Any] = field(default_factory=dict)
    planner: Dict[str, Any] = field(default_factory=dict)

    @property
    def slot_chars(self) -> int:
        return int(self.planner.get("slot_chars", 50))

    @property
    def slot_count(self) -> int:
        return int(self.planner.get("slots", 7))


def _as_weighted(entries: Any, what: str) -> List[WeightedMatch]:
    if entries is None:
        return []
    if not isinstance(entries, list):
        raise RulesError(f"'{what}' should be a list, got {type(entries).__name__}")
    out = []
    for i, item in enumerate(entries):
        if not isinstance(item, dict) or "pattern" not in item:
            raise RulesError(f"'{what}[{i}]' needs at least a 'pattern' key")
        out.append(
            WeightedMatch(
                pattern=_Pattern(item),
                weight=int(item.get("weight", 0)),
                reason=str(item.get("reason", "")),
            )
        )
    return out


def parse_rules(data: Any, source: str) -> Rules:
    if not isinstance(data, dict):
        raise RulesError(f"{source}: rules file must be a YAML mapping at the top level")

    profile = data.get("profile") or {}
    scoring = data.get("scoring") or {}
    risk = data.get("risk") or {}
    if not isinstance(profile, dict) or not isinstance(scoring, dict) or not isinstance(risk, dict):
        raise RulesError(f"{source}: 'profile', 'scoring' and 'risk' must be mappings")

    categories = data.get("categories") or []
    if not isinstance(categories, list):
        raise RulesError(f"{source}: 'categories' must be a list")

    risk_rules = []
    for item in risk.get("rules", []) or []:
        if not isinstance(item, dict) or "pattern" not in item or "id" not in item:
            raise RulesError(f"{source}: every risk rule needs 'id' and 'pattern'")
        risk_rules.append(
            RiskRule(
                id=str(item["id"]),
                severity=str(item.get("severity", "medium")).lower(),
                pattern=_Pattern(item),
                reason=str(item.get("reason", "")),
            )
        )

    return Rules(
        raw=data,
        source=source,
        profile=profile if isinstance(profile, dict) else {},
        stopwords=set(str(w).lower() for w in (profile.get("stopwords") or [])),
        base_score=int(scoring.get("base", 50)),
        boosts=_as_weighted(scoring.get("boosts"), "scoring.boosts"),
        penalties=_as_weighted(scoring.get("penalties"), "scoring.penalties"),
        length=scoring.get("length") or {},
        risk_rules=risk_rules,
        categories=[c for c in categories if isinstance(c, dict) and c.get("name")],
        clustering=data.get("clustering") or {},
        planner=data.get("planner") or {},
    )


def load_rules(path: Optional[str] = None) -> Rules:
    """Load a custom rules file, or the built-in default when *path* is None."""
    if path is None:
        source = "bookkeywordlab/defaults/rules.yaml (built-in)"
        try:
            text = resources.files("bookkeywordlab.defaults").joinpath("rules.yaml").read_text("utf-8")
        except FileNotFoundError as exc:  # pragma: no cover - packaging problem
            raise RulesError(f"built-in rules file missing: {exc}") from exc
    else:
        source = str(path)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            raise RulesError(f"cannot read rules file {path}: {exc}") from exc

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RulesError(f"{source}: invalid YAML ({exc})") from exc
    return parse_rules(data, source)
