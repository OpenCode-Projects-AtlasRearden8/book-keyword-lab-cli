"""Render the plan as copy-paste text, markdown, or JSON."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Callable, Dict

from .planner import KeywordPlan, plan_to_dict
from . import __version__


class ExportError(ValueError):
    pass


def _generated() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def render_text(plan: KeywordPlan, generated: str = "") -> str:
    generated = generated or _generated()
    lines: list = []
    bar = "=" * 66
    lines.append(bar)
    lines.append("BOOK KEYWORD LAB - COPY-PASTE EXPORT (v" + __version__ + ")")
    lines.append(f"Generated: {generated}")
    if plan.book_title:
        lines.append(f"Book: {plan.book_title}")
    if plan.profile_name:
        lines.append(f"Profile: {plan.profile_name}")
    lines.append(bar)

    slot_header = (
        "SEVEN KEYWORD SLOTS (50 characters each)"
        if len(plan.slots) == 7
        else f"KEYWORD SLOTS ({len(plan.slots)} slots, 50 characters each)"
    )
    lines.append("")
    lines.append(slot_header)
    lines.append("Paste one phrase into each KDP keyword slot (50 characters max each).")
    lines.append("")
    for s in plan.slots:
        if s.phrase is None:
            lines.append(f"  {s.slot}. (open - add candidate terms or run: bkwl brainstorm)")
        else:
            lines.append(f"  {s.slot}. {s.phrase}")

    lines.append("")
    lines.append("CATEGORY SHORTLIST - pick up to three in KDP (verify the live names there):")
    for c in plan.categories:
        marker = {"primary": "*", "alternate": "+"}.get(c.kind, "-")
        lines.append(f"  {marker} [{c.kind}] {c.name}")
        lines.append(f"      why: {c.note}")

    lines.append("")
    if plan.skipped:
        lines.append("SKIPPED CANDIDATES (see reasoning):")
        for term, reason in plan.skipped:
            lines.append(f"  - {term}")
            lines.append(f"      ({reason})")
    else:
        lines.append("SKIPPED CANDIDATES: none - every candidate passed the risk screens.")

    lines.append("")
    lines.append("REASONING NOTES (why each slot earned its place):")
    for s in plan.slots:
        if s.phrase is None:
            continue
        head = f"slot {s.slot} - {s.phrase} (score {s.score}/100)"
        lines.append(f"  {head}")
        for note in s.notes:
            lines.append(f"    - {note}")
    lines.append(bar)
    return "\n".join(lines)


def plan_profile_hint(plan: KeywordPlan) -> str:
    """Kept for the JSON export consumers that peek at slot width."""
    return "50 characters each"


def render_markdown(plan: KeywordPlan, generated: str = "") -> str:
    generated = generated or _generated()
    out: list = []
    out.append(f"# Book Keyword Lab export - {generated}")
    if plan.book_title:
        out.append(f"\n**Book:** {plan.book_title}")
    if plan.profile_name:
        out.append(f"**Profile:** {plan.profile_name}")

    out.append("\n## Seven keyword slots (50 chars each)\n")
    for s in plan.slots:
        phrase = s.phrase if s.phrase is not None else "(open)"
        out.append(f"{s.slot}. `{phrase}`")
        for note in s.notes:
            out.append(f"   - {note}")

    out.append("\n## Category shortlist (pick up to three; verify live names in KDP)\n")
    for c in plan.categories:
        out.append(f"- **{c.name}** ({c.kind}, fit {c.score})")
        out.append(f"  - {c.note}")

    out.append("\n## Skipped candidates\n")
    if plan.skipped:
        for term, reason in plan.skipped:
            out.append(f"- `{term}` - {reason}")
    else:
        out.append("None - every candidate passed the risk screens.")
    return "\n".join(out) + "\n"


def render_json(plan: KeywordPlan, generated: str = "") -> str:
    return json.dumps(plan_to_dict(plan), indent=2, ensure_ascii=False) + "\n"


_RENDERERS: Dict[str, Callable[[KeywordPlan], str]] = {
    "text": render_text,
    "markdown": render_markdown,
    "json": render_json,
}


def render(plan: KeywordPlan, fmt: str = "text") -> str:
    fmt = (fmt or "text").lower()
    if fmt not in _RENDERERS:
        raise ExportError(f"unknown format '{fmt}'; expected text, markdown or json")
    return _RENDERERS[fmt](plan)
