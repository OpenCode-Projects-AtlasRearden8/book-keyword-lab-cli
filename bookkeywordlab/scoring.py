"""Heuristic scoring driven entirely by the local rules file."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .rules import Rules
from .textutil import tokenize


@dataclass
class ScoredTerm:
    term: str          # as the user typed it
    normalized: str    # lowercase canonical form
    score: int         # clamped 0..100
    notes: List[str] = field(default_factory=list)
    tokens: frozenset = frozenset()

    @property
    def char_count(self) -> int:
        return len(self.term)


def score_term(term: str, rules: Rules) -> ScoredTerm:
    """Return an explained heuristic score for one candidate phrase."""
    text = (term or "").strip()
    notes: List[str] = []
    score = rules.base_score

    all_tokens = tokenize(text)
    stopwords = rules.stopwords
    meaningful = [t for t in all_tokens if t not in stopwords]
    token_set = frozenset(meaningful) or frozenset(all_tokens)

    length = rules.length
    min_chars = int(length.get("min_chars", 3))
    sweet_min = int(length.get("sweet_min_words", 2))
    sweet_max = int(length.get("sweet_max_words", 6))
    chars = len(text)
    words = len(all_tokens)

    if chars < min_chars:
        score -= 8
        notes.append(f"-8: {chars} char(s) is too short to be a real search phrase")
    if chars > rules.slot_chars:
        score -= 8
        notes.append(
            f"-8: {chars} chars won't fit one {rules.slot_chars}-character KDP slot"
        )
    if sweet_min <= words <= sweet_max:
        score += 5
        notes.append(
            f"+5: {words} words sits in the 2-{sweet_max} word search-phrase sweet spot"
        )
    else:
        penalty = 3 if words < sweet_min else 2
        score -= penalty
        if words < sweet_min:
            notes.append(f"-{penalty}: only {words} word - broad and hard to rank for")
        else:
            notes.append(f"-{penalty}: {words} words is long for a buyer to type")

    for item in rules.boosts:
        hit = item.pattern.search(text)
        if hit:
            score += item.weight
            note = f"{item.weight:+d} matches '{hit}'"
            if item.reason:
                note += f" ({item.reason})"
            notes.append(note)

    for item in rules.penalties:
        hit = item.pattern.search(text)
        if hit:
            score += item.weight
            note = f"{item.weight:+d} matches '{hit}'"
            if item.reason:
                note += f" ({item.reason})"
            notes.append(note)

    score = max(0, min(100, score))
    return ScoredTerm(
        term=text,
        normalized=" ".join(all_tokens),
        score=score,
        notes=notes,
        tokens=token_set,
    )


def score_candidates(terms: List[str], rules: Rules) -> List[ScoredTerm]:
    """Score and sort candidates (best first; ties break alphabetically)."""
    scored = [score_term(t, rules) for t in terms]
    scored.sort(key=lambda s: (-s.score, s.normalized))
    return scored
