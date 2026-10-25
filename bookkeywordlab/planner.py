"""Draft the seven-keyword slot plan and a category shortlist, with reasoning notes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .risk import RiskFlag, assess_risk, high_risk_flags
from .rules import Rules
from .scoring import ScoredTerm
from .clustering import Cluster
from .textutil import tokenize

PRIMARY = "primary"
ALTERNATE = "alternate"


@dataclass
class SlotPlan:
    slot: int
    phrase: Optional[str]          # None means the slot is still open
    score: Optional[int] = None
    cluster: Optional[str] = None
    new_words: List[str] = field(default_factory=list)
    repeated_words: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    risks: List[RiskFlag] = field(default_factory=list)


@dataclass
class CategoryPick:
    name: str
    score: int
    kind: str                      # "primary" or "alternate"
    matched: List[str] = field(default_factory=list)
    note: str = ""


@dataclass
class KeywordPlan:
    book_title: str
    profile_name: str
    slots: List[SlotPlan] = field(default_factory=list)
    categories: List[CategoryPick] = field(default_factory=list)
    skipped: List[Tuple[str, str]] = field(default_factory=list)


def _category_picks(scored: List[ScoredTerm], rules: Rules) -> List[CategoryPick]:
    n = max(len(scored), 1)
    picks: List[Tuple[Dict, int, List[str]]] = []
    for cat in rules.categories:
        fit_terms = [str(t).lower().strip() for t in (cat.get("fit_terms") or [])]
        fit_tokens: set = set()
        for ft in fit_terms:
            fit_tokens |= set(tokenize(ft))
        matched = [s.term for s in scored if s.tokens and (s.tokens & fit_tokens)]
        phrase_hits = sum(1 for ft in fit_terms if any(f" {ft} " in f" {s.normalized} " for s in scored))
        weight = float(cat.get("weight", 1.0))
        score = int(round((len(matched) / n) * 100 * weight) + phrase_hits * 2)
        picks.append((cat, score, matched))
    picks.sort(key=lambda t: (-t[1], str(t[0].get("name", ""))))

    planner_cfg = rules.planner or {}
    primary_n = int(planner_cfg.get("primary_categories", 3))
    alternate_n = int(planner_cfg.get("alternate_categories", 2))

    out: List[CategoryPick] = []
    for i, (cat, score, matched) in enumerate(picks):
        kind = PRIMARY if i < primary_n else (ALTERNATE if i < primary_n + alternate_n else "extra")
        shown = matched[:6] + (["..."] if len(matched) > 6 else [])
        note = str(cat.get("note", ""))
        reason = f"{len(matched)} of {len(scored)} candidates relate"
        if matched:
            reason += ": " + ", ".join(str(x) for x in shown)
        out.append(
            CategoryPick(
                name=str(cat.get("name", "")),
                score=score,
                kind=kind,
                matched=matched,
                note=note,
            )
        )
        out[-1].note = f"{reason}. {note}".strip(". ")
    return [p for p in out if p.kind in (PRIMARY, ALTERNATE)]


def build_plan(
    scored: List[ScoredTerm],
    clusters: List[Cluster],
    rules: Rules,
    book_title: str = "",
) -> KeywordPlan:
    """Assemble a conservative, reasoned plan: one phrase per cluster first, then backfill."""
    slot_count = rules.slot_count
    slot_chars = rules.slot_chars

    cluster_of: Dict[str, str] = {
        m.normalized: c.label for c in clusters for m in c.members
    }

    eligible: List[Tuple[ScoredTerm, List[RiskFlag], str]] = []
    skipped: List[Tuple[str, str]] = []
    for item in scored:
        phrase = item.term
        if len(phrase) > slot_chars:
            skipped.append((phrase, f"{len(phrase)} chars is over the {slot_chars}-char slot limit"))
            continue
        flags = assess_risk(phrase, rules)
        highs = high_risk_flags(flags)
        if highs:
            worst = highs[0]
            skipped.append(
                (phrase, f"high-risk '{worst.rule_id}': {worst.reason or 'see rules file'}")
            )
            continue
        eligible.append((item, flags, cluster_of.get(item.normalized, "unclustered")))

    # Pass 1: one phrase per cluster, walking candidates best-score-first.
    order: List[Tuple[ScoredTerm, List[RiskFlag], str]] = []
    seen: set = set()
    remaining: List[Tuple[ScoredTerm, List[RiskFlag], str]] = []
    for entry in eligible:
        label = entry[2]
        if label not in seen:
            seen.add(label)
            order.append(entry)
        else:
            remaining.append(entry)

    # Pass 2: backfill by whichever phrase adds the most fresh words (varied coverage).
    used_words: set = set()
    for item, _flags, _label in order:
        used_words |= set(item.tokens)

    while len(order) < slot_count and remaining:
        def backfill_key(entry):
            item = entry[0]
            fresh = len(set(item.tokens) - used_words)
            return (-fresh, -item.score, item.normalized)

        remaining.sort(key=backfill_key)
        pick = remaining.pop(0)
        order.append(pick)
        used_words |= set(pick[0].tokens)

    slots: List[SlotPlan] = []
    chosen = order[:slot_count]
    chosen.sort(key=lambda entry: (-entry[0].score, entry[0].normalized))
    used_words = set()
    for i, (item, flags, label) in enumerate(chosen, start=1):
        phrase = item.term
        tokens = set(item.tokens)
        new = sorted(tokens - used_words)
        repeated = sorted(tokens & used_words)
        notes = [
            f"cluster: {label}" if label != "unclustered" else "cluster: (stood alone)",
        ]
        if repeated:
            notes.append("shares words with an earlier slot: " + ", ".join(repeated))
        else:
            notes.append("adds fresh words to the plan")
        for flag in flags:
            if flag.severity in ("medium", "low"):
                notes.append(f"caution ({flag.rule_id}): {flag.reason}")
        notes.extend(item.notes[:3])
        slots.append(
            SlotPlan(
                slot=i,
                phrase=phrase,
                score=item.score,
                cluster=label,
                new_words=new,
                repeated_words=repeated,
                notes=notes,
                risks=flags,
            )
        )
        used_words |= tokens

    for i in range(len(chosen) + 1, slot_count + 1):
        slots.append(
            SlotPlan(
                slot=i,
                phrase=None,
                notes=["open: add more candidate terms (bkwl add ...) or run bkwl brainstorm"],
            )
        )

    plan = KeywordPlan(
        book_title=book_title,
        profile_name=str(rules.profile.get("name", "")),
        slots=slots,
        categories=_category_picks(scored, rules),
        skipped=skipped,
    )
    return plan


def plan_to_dict(plan: KeywordPlan) -> Dict:
    return {
        "book_title": plan.book_title,
        "profile_name": plan.profile_name,
        "slots": [
            {
                "slot": s.slot,
                "phrase": s.phrase,
                "score": s.score,
                "cluster": s.cluster,
                "new_words": s.new_words,
                "repeated_words": s.repeated_words,
                "notes": s.notes,
                "risks": [
                    {"rule_id": f.rule_id, "severity": f.severity, "matched": f.matched}
                    for f in s.risks
                ],
            }
            for s in plan.slots
        ],
        "categories": [
            {"name": c.name, "kind": c.kind, "score": c.score, "note": c.note}
            for c in plan.categories
        ],
        "skipped": [{"term": t, "reason": r} for t, r in plan.skipped],
    }
