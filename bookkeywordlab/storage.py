"""Local JSON state file: the candidates and book title live here, on your disk."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .textutil import normalize_term

DEFAULT_STATE_FILENAME = "book-keyword-lab-state.json"
STATE_VERSION = 1


class StorageError(Exception):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class State:
    path: str
    book_title: str = ""
    candidates: Dict[str, dict] = field(default_factory=dict)
    saved_at: str = ""

    @classmethod
    def load(cls, path: Optional[str] = None) -> "State":
        path = path or DEFAULT_STATE_FILENAME
        state = cls(path=path)
        if not os.path.exists(path):
            return state
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError) as exc:
            raise StorageError(
                f"could not read state file {path} ({exc}); "
                f"repair or delete it, then run: bkwl init"
            ) from exc
        if data.get("version", STATE_VERSION) > STATE_VERSION:
            raise StorageError(
                f"{path} was written by a newer Book Keyword Lab version; please upgrade"
            )
        state.book_title = str(data.get("book_title", "") or "")
        cands = data.get("candidates", {}) or {}
        if isinstance(cands, list):  # tolerate older list-form
            cands = {normalize_term(c) if isinstance(c, str) else "": {} for c in cands}
        for key, val in cands.items():
            if isinstance(val, dict) and "term" in val:
                state.candidates[str(key)] = val
        return state

    def save(self) -> None:
        self.saved_at = _now_iso()
        data = {
            "version": STATE_VERSION,
            "saved_at": self.saved_at,
            "book_title": self.book_title,
            "candidates": self.candidates,
        }
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
            os.replace(tmp, self.path)
        except OSError as exc:
            raise StorageError(f"could not save state file {self.path}: {exc}") from exc

    def exists(self) -> bool:
        return os.path.exists(self.path)

    def set_title(self, title: str) -> None:
        self.book_title = title.strip()

    def add_terms(self, terms: List[str], source: str = "manual") -> Tuple[List[str], List[str]]:
        """Add phrases; returns (added_display_terms, already_present_terms)."""
        added: List[str] = []
        present: List[str] = []
        for term in terms:
            text = term.strip()
            if not text:
                continue
            key = normalize_term(text)
            if not key:
                present.append(text)
                continue
            if key in self.candidates:
                entry = self.candidates[key]
                if source and source not in entry.get("sources", []):
                    entry.setdefault("sources", []).append(source)
                present.append(text)
                continue
            self.candidates[key] = {"term": text, "sources": [source] if source else [], "added": _now_iso()}
            added.append(text)
        return added, present

    def remove_terms(self, terms: List[str]) -> Tuple[List[str], List[str]]:
        """Remove by exact match first, then by forgiving substring match."""
        removed: List[str] = []
        missing: List[str] = []
        display = {key: val.get("term", key) for key, val in self.candidates.items()}
        keys_removed: set = set()
        for term in terms:
            key = normalize_term(term)
            exact = key in self.candidates and key not in keys_removed
            if exact:
                matched = [key]
            else:
                matched = [k for k in self.candidates if key and key in k and k not in keys_removed]
            if not matched:
                missing.append(term.strip())
                continue
            for k in matched:
                keys_removed.add(k)
                removed.append(display.get(k, k))
                self.candidates.pop(k, None)
        return removed, missing

    def terms(self) -> List[str]:
        """Display terms in insertion (pasting) order."""
        return [val.get("term", key) for key, val in self.candidates.items()]


def default_state_path() -> str:
    return os.path.join(os.getcwd(), DEFAULT_STATE_FILENAME)
