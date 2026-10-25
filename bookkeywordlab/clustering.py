"""Group related candidate terms so the plan can cover more search intents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from .rules import Rules
from .scoring import ScoredTerm


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _containment(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def similarity(a: frozenset, b: frozenset, measure: str) -> float:
    return _containment(a, b) if measure == "containment" else _jaccard(a, b)


@dataclass
class Cluster:
    label: str                       # the highest-scoring member, as typed
    members: List[ScoredTerm] = field(default_factory=list)

    @property
    def best(self) -> ScoredTerm:
        return self.members[0]

    @property
    def size(self) -> int:
        return len(self.members)


def cluster_terms(
    scored: Sequence[ScoredTerm],
    rules: Rules,
    threshold: Optional[float] = None,
    measure: Optional[str] = None,
) -> List[Cluster]:
    """Greedy, deterministic clustering: join a term to the closest cluster or start a new one.

    *scored* must already be sorted best-first (as score_candidates does).
    """
    cfg = rules.clustering or {}
    th = float(cfg.get("threshold", 0.5)) if threshold is None else float(threshold)
    how = (measure or str(cfg.get("measure", "containment"))).lower()

    clusters: List[Cluster] = []
    for item in scored:
        best: Optional[Cluster] = None
        best_sim = 0.0
        for cluster in clusters:
            sim = max(
                similarity(item.tokens, m.tokens, how) for m in cluster.members
            )
            if sim > best_sim:
                best, best_sim = cluster, sim
        if best is not None and best_sim >= th:
            best.members.append(item)
        else:
            clusters.append(Cluster(label=item.term, members=[item]))
    return clusters
