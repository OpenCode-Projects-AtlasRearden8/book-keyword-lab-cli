"""The bkwl command line interface: paste, score, cluster, screen, plan, export."""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

from . import __version__
from .brainstorm import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT,
    BrainstormError,
    brainstorm,
    list_models,
)
from .clustering import cluster_terms
from .export import ExportError, render
from .planner import build_plan
from .risk import assess_risk, badge
from .rules import RulesError, load_rules
from .scoring import score_candidates
from .storage import DEFAULT_STATE_FILENAME, State, StorageError, default_state_path
from .textutil import split_candidates

EPILOG = """\
a calm little workflow:
  bkwl init -t "The Massive AI Manual"
  bkwl add                (paste candidate lines, then Ctrl-D / Ctrl-Z to end)
  bkwl add "ai for beginners" "local ai basics" "guaranteed bestseller"
  bkwl score              (explained scores from your rules file)
  bkwl cluster            (related terms grouped, so slots can spread out)
  bkwl plan               (the seven-slot draft + category shortlist, with reasons)
  bkwl export -f markdown -o keywords.md
brainstorm (optional, local-first, never needs a key):
  bkwl models             (list models from the endpoint)
  bkwl brainstorm         (asks http://localhost:11434/v1 by default; any --base-url works)
"""

NO_CANDIDATES_HINT = (
    "no candidates yet. paste some with:  bkwl add   "
    "(type or paste lines, end with Ctrl-D / Ctrl-Z), "
    "or run:  bkwl add \"ai for beginners\"  - brainstorming needs candidates too."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bkwl",
        description=(
            "Book Keyword Lab - pick strong book keywords and categories with local, "
            "explainable heuristics. No accounts, no keys, no cloud: everything stays "
            "in this folder."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"bkwl {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    def common(sp: argparse.ArgumentParser) -> argparse.ArgumentParser:
        sp.add_argument("--rules", metavar="FILE", help="rules file (YAML); default is the built-in file")
        sp.add_argument("--state", metavar="FILE", help=f"state file (default: {DEFAULT_STATE_FILENAME})")
        return sp

    def with_endpoint(sp: argparse.ArgumentParser) -> argparse.ArgumentParser:
        sp.add_argument("--base-url", metavar="URL", default=None,
                        help=f"OpenAI-compatible base URL (default: {DEFAULT_BASE_URL}); never needs a key")
        sp.add_argument("--model", "-m", metavar="NAME", default=None, help=f"model name (default: {DEFAULT_MODEL})")
        sp.add_argument("--timeout", type=float, default=None, help=f"seconds to wait (default: {int(DEFAULT_TIMEOUT)})")
        return sp

    sp_init = sub.add_parser("init", help="start a local state file for your book")
    sp_init.add_argument("--title", "-t", default="", help="book title stored with the state (optional)")
    common(sp_init)

    sp_add = sub.add_parser("add", help="add candidate keyword phrases (paste-friendly)")
    sp_add.add_argument("terms", nargs="*",
                        help='phrases like "ai for beginners"; use - (or leave empty in a pipe/script) to paste from stdin')
    sp_add.add_argument("--source", "-s", default="manual", help="label for where these came from (default: manual)")
    common(sp_add)

    sp_list = sub.add_parser("list", help="show candidates with quick scores and risk badges")
    common(sp_list)

    sp_remove = sub.add_parser("remove", help="remove candidates (exact match first, then close match)")
    sp_remove.add_argument("terms", nargs="+", help="phrases to remove")
    common(sp_remove)

    sp_score = sub.add_parser("score", help="score candidates with rules-file heuristics")
    sp_score.add_argument("--min-score", type=int, default=0, help="only show scores at or above this (default: 0)")
    sp_score.add_argument("--no-notes", action="store_true", help="compact table, skip the explained notes")
    common(sp_score)

    sp_cluster = sub.add_parser("cluster", help="group related terms so slots can spread out")
    common(sp_cluster)

    sp_risk = sub.add_parser("risk", help="flag risky wording (brands, claims, personal data, spam)")
    common(sp_risk)

    sp_plan = sub.add_parser("plan", help="draft the seven-keyword slot plan + category shortlist")
    common(sp_plan)

    sp_export = sub.add_parser("export", help="copy-paste export: text, markdown, or JSON")
    sp_export.add_argument("--format", "-f", choices=["text", "markdown", "json"], default="text",
                           help="format (default: text)")
    sp_export.add_argument("--out", "-o", metavar="FILE", default=None, help="write to a file instead of stdout")
    common(sp_export)

    sp_brain = sub.add_parser("brainstorm", help="optional idea pass via a keyless OpenAI-compatible endpoint")
    sp_brain.add_argument("prompt", nargs="*", default=[], help="optional theme; default comes from your rules file")
    sp_brain.add_argument("--count", type=int, default=12, help="how many phrases to request (default: 12)")
    sp_brain.add_argument("--no-add", action="store_true", help="show suggestions but do not add them to state")
    common(sp_brain)
    with_endpoint(sp_brain)

    sp_models = sub.add_parser("models", help="list models the endpoint offers (nice for --model)")
    common(sp_models)
    with_endpoint(sp_models)

    sp_reset = sub.add_parser("reset", help="delete the state file and start clean")
    sp_reset.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    common(sp_reset)

    return parser


def _state(args) -> State:
    return State.load(getattr(args, "state", None))


def _rules(args):
    return load_rules(getattr(args, "rules", None))


def _read_stdin_once() -> str:
    """Read pasted input to EOF. Ctrl-C behaves like Ctrl-D: keep what arrived."""
    print("(pasting mode: type or paste lines, end with Ctrl-D / Ctrl-Z then Enter)",
          file=sys.stderr)
    chunks: List[str] = []
    try:
        chunks.append(sys.stdin.read())
    except (KeyboardInterrupt, EOFError):
        pass
    return "\n".join(chunks)


def cmd_init(args) -> int:
    state = _state(args)
    existed = state.exists()
    state.set_title(args.title or state.book_title or "")
    state.save()
    if not existed:
        print(f"started fresh state at {state.path}")
    else:
        print(f"state ready: {state.path}")
    print(f"book title: {state.book_title or '(not set; rerun with -t \"Title\")'}")
    print(f"candidates: {len(state.candidates)}")
    print("next:  bkwl add     (paste lines, end with Ctrl-D / Ctrl-Z)")
    return 0


def cmd_add(args) -> int:
    state = _state(args)
    payloads: List[str] = list(args.terms)
    if "-" in payloads:
        payloads = [p for p in payloads if p != "-"]
        payloads.append(_read_stdin_once())
    elif not payloads and not sys.stdin.isatty():
        payloads.append(_read_stdin_once())
    if not payloads:
        print("nothing to add.")
        print('try:  bkwl add "ai for beginners" "local ai basics"')
        print("or:   bkwl add      (then paste lines, end with Ctrl-D / Ctrl-Z)")
        return 1
    terms: List[str] = []
    for payload in payloads:
        terms.extend(split_candidates(payload))
    added, present = state.add_terms(terms, source=getattr(args, "source", "manual"))
    state.save()
    if added:
        print(f"added {len(added)} candidate(s):")
        for term in added:
            print(f"  + {term}")
    if present:
        print(f"already in the list: {len(present)} (skipped duplicates, case-insensitive)")
    if not added and present:
        print("no changes saved.")
    print("next:  bkwl score   (see explained scores)")
    return 0


def cmd_list(args) -> int:
    state = _state(args)
    if not state.candidates:
        print(NO_CANDIDATES_HINT)
        return 0
    rules = _rules(args)
    scored = {s.normalized: s for s in score_candidates(state.terms(), rules)}
    print(f"{'#':>3}  {'score':>5}  {'risk':>4}  {'chars':>5}  term / sources")
    print("-" * 72)
    for i, (key, entry) in enumerate(state.candidates.items(), start=1):
        s = scored[key]
        flags = assess_risk(s.term, rules)
        sources = ", ".join(entry.get("sources", []) or ["manual"])
        print(f"{i:>3}  {s.score:>4}/100  {badge(flags):>4}  {s.char_count:>5}  {s.term}")
        print(f"{'':>28}{sources}")
    print(f"\n{len(state.candidates)} candidate(s). next:  bkwl plan   (draft slots + categories)")
    return 0


def cmd_remove(args) -> int:
    state = _state(args)
    removed, missing = state.remove_terms(args.terms)
    state.save()
    if removed:
        print(f"removed {len(removed)}:")
        for term in removed:
            print(f"  - {term}")
    for term in missing:
        print(f"not found: {term}")
    return 0


def cmd_score(args) -> int:
    state = _state(args)
    if not state.candidates:
        print(NO_CANDIDATES_HINT)
        return 1
    rules = _rules(args)
    scored = [s for s in score_candidates(state.terms(), rules) if s.score >= args.min_score]
    if not scored:
        print(f"nothing scored at or above {args.min_score}; try a lower --min-score.")
        return 0
    print(f"{len(scored)} candidate(s), scored by {rules.source}")
    for i, s in enumerate(scored, start=1):
        flags = assess_risk(s.term, rules)
        marker = f" [{badge(flags)}risk]" if flags else ""
        print(f"{i:>3}. {s.score:>3}/100  {s.term}{marker}  ({s.char_count} chars)")
        if not args.no_notes:
            for note in s.notes:
                print(f"      - {note}")
            for flag in flags:
                print(f"      ! {flag.severity} ({flag.rule_id}): {flag.reason}")
    print("\nscore = 50 base " + "+ boosts - penalties from your rules file; "
          "brands and claims are screened by:  bkwl risk")
    return 0


def cmd_cluster(args) -> int:
    state = _state(args)
    if not state.candidates:
        print(NO_CANDIDATES_HINT)
        return 1
    rules = _rules(args)
    scored = score_candidates(state.terms(), rules)
    clusters = cluster_terms(scored, rules)
    print(f"{len(scored)} candidate(s) -> {len(clusters)} cluster(s) "
          f"(measure: {str(rules.clustering.get('measure', 'containment'))}, "
          f"threshold: {rules.clustering.get('threshold', 0.5)})")
    for i, cluster in enumerate(clusters, start=1):
        print(f"\n{i}. {cluster.label}  (best score {cluster.best.score}/100, {cluster.size} member(s))")
        for member in cluster.members:
            print(f"     - {member.term} ({member.score}/100)")
    return 0


def cmd_risk(args) -> int:
    state = _state(args)
    if not state.candidates:
        print(NO_CANDIDATES_HINT)
        return 1
    rules = _rules(args)
    flagged = 0
    for term in state.terms():
        flags = assess_risk(term, rules)
        if not flags:
            continue
        flagged += 1
        print(f"{term}")
        for flag in flags:
            print(f"  ! {flag.severity} ({flag.rule_id}) matched '{flag.matched}': {flag.reason}")
    if not flagged:
        print("no risky wording found - nice work. screens come from your rules file "
              "(ids: " + ", ".join(r.id for r in rules.risk_rules) + ").")
    else:
        print(f"\n{flagged} term(s) flagged. high-risk terms are excluded from slots by bkwl plan.")
    return 0


def _load_plan(args):
    state = _state(args)
    if not state.candidates:
        print(NO_CANDIDATES_HINT)
        return None
    rules = _rules(args)
    scored = score_candidates(state.terms(), rules)
    clusters = cluster_terms(scored, rules)
    return build_plan(scored, clusters, rules, book_title=state.book_title)


def cmd_plan(args) -> int:
    plan = _load_plan(args)
    if plan is None:
        return 1
    print(render(plan, "text"))
    return 0


def cmd_export(args) -> int:
    plan = _load_plan(args)
    if plan is None:
        return 1
    text = render(plan, args.format)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        out_path = os.path.abspath(args.out)
        try:
            size = os.path.getsize(out_path)
            print(f"wrote {out_path} ({args.format}, {size} bytes) - paste it into KDP as-is.")
        except OSError:  # pragma: no cover
            print(f"wrote {out_path} ({args.format})")
    else:
        print(text)
    return 0


def cmd_brainstorm(args) -> int:
    state = _state(args)
    rules = _rules(args)
    theme = " ".join(args.prompt).strip() or str(rules.profile.get("brainstorm_theme", "")).strip()
    if not theme:
        theme = "beginner-friendly AI book keywords"
    base_url = args.base_url or DEFAULT_BASE_URL
    model = args.model or DEFAULT_MODEL
    timeout = args.timeout if args.timeout is not None else DEFAULT_TIMEOUT
    print(f"brainstorming with {model} at {base_url} (keyless; nothing leaves your machine "
          "except this request)", file=sys.stderr)
    try:
        phrases = brainstorm(
            theme,
            seed_terms=state.terms(),
            base_url=base_url,
            model=model,
            timeout=timeout,
            count=args.count,
        )
    except BrainstormError as exc:
        print(f"brainstorm unavailable: {exc}")
        if exc.hint:
            print(f"hint: {exc.hint}")
        return 1
    if not phrases:
        print("the model did not give usable phrases; try another model (bkwl models).")
        return 1
    print(f"{len(phrases)} suggestion(s), scored and screened with your rules file:")
    for i, s in enumerate(score_candidates(phrases, rules), start=1):
        flags = assess_risk(s.term, rules)
        marker = f" [{badge(flags)}risk]" if flags else ""
        print(f"{i:>3}. {s.score:>3}/100  {s.term}{marker}")
    if args.no_add:
        print("(not added: --no-add)")
    else:
        added, present = state.add_terms(phrases, source=f"brainstorm:{model}")
        state.save()
        print(f"added {len(added)} new candidate(s)"
              + (f", {len(present)} already present" if present else "")
              + "; saved. next:  bkwl plan")
    return 0


def cmd_models(args) -> int:
    base_url = args.base_url or DEFAULT_BASE_URL
    timeout = args.timeout if args.timeout is not None else 20.0
    try:
        models = list_models(base_url, timeout=timeout)
    except BrainstormError as exc:
        print(f"could not list models: {exc}")
        if exc.hint:
            print(f"hint: {exc.hint}")
        return 1
    if not models:
        print("endpoint returned no model ids.")
        return 1
    print(f"models at {base_url}:")
    for m in models:
        print(f"  - {m}")
    print("use one with:  bkwl brainstorm -m " + models[0])
    return 0


def cmd_reset(args) -> int:
    path = args.state or default_state_path()
    if not os.path.exists(path):
        print(f"nothing to reset ({path} does not exist).")
        return 0
    if not args.yes:
        if sys.stdin.isatty():
            answer = input(f"delete {path}? [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                print("cancelled - nothing deleted.")
                return 0
        else:
            print(f"refusing to delete {path} without --yes (non-interactive).")
            return 1
    try:
        os.remove(path)
    except OSError as exc:  # pragma: no cover
        print(f"could not delete {path}: {exc}")
        return 1
    print(f"deleted {path}. fresh start whenever you are ready: bkwl init -t \"Your Title\"")
    return 0


COMMANDS = {
    "init": cmd_init,
    "add": cmd_add,
    "list": cmd_list,
    "remove": cmd_remove,
    "score": cmd_score,
    "cluster": cmd_cluster,
    "risk": cmd_risk,
    "plan": cmd_plan,
    "export": cmd_export,
    "brainstorm": cmd_brainstorm,
    "models": cmd_models,
    "reset": cmd_reset,
}


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = COMMANDS[args.command]
    try:
        return handler(args)
    except (RulesError, StorageError, ExportError) as exc:
        print(f"error: {exc}")
        return 1
    except KeyboardInterrupt:  # pragma: no cover - user interrupt
        print("\ninterrupted.")
        return 130
