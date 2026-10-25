"""Small text helpers shared by every module."""

from __future__ import annotations

import re
from typing import List, Set

_TOKEN_RE = re.compile(r"[a-z0-9#+]+")
_BULLET_RE = re.compile(r"^\s*(?:[-\-\*\u2022#>]|\d+[.)])\s+")


def tokenize(text: str) -> List[str]:
    """Lowercase tokens, keeping a few trusty marks like + and # (so 'C++' stays intact)."""
    return _TOKEN_RE.findall(text.lower())


def normalize_term(text: str) -> str:
    """Canonical, case-insensitive form used to de-duplicate candidates."""
    return " ".join(tokenize(text))


def content_tokens(text: str, stopwords: Set[str]) -> List[str]:
    return [t for t in tokenize(text) if t not in stopwords]


def split_candidates(raw: str) -> List[str]:
    """Turn pasted text into candidate phrases.

    Splits on newlines, commas, semicolons, tabs and pipes, then strips common
    bullet/numbering prefixes and surrounding quotes. Everything is kept in the
    order it arrived, and blank bits are dropped.
    """
    out: List[str] = []
    for part in re.split(r"[\n,;\t|]+", raw or ""):
        s = part.strip()
        if not s:
            continue
        s = _BULLET_RE.sub("", s)
        s = s.strip().strip("\"'")
        s = s.strip()
        # A second pass handles "1) foo" style numbering without whitespace.
        if s and _BULLET_RE.match(s):
            s = _BULLET_RE.sub("", s).strip()
        if s:
            out.append(s)
    return out
