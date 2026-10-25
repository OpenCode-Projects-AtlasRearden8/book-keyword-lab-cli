# Book Keyword Lab (bkwl)

A local-first author CLI for choosing **book keywords and categories** for your
KDP-style listing. You paste candidate phrases, the CLI scores them with an
**editable rule file**, clusters related terms, flags risky wording, drafts a
**seven-keyword slot plan** plus a **category shortlist**, and hands you a
clean copy-paste export - with the reasoning spelled out like a friend would,
step by step, never condescending.

Built and maintained by **Asdale Dynamics, LLC** (Dylan Asdale) as part of the
toolset around *The Massive AI Manual* (hub: https://dylanasdale.github.io).
 MIT License - see `LICENSE`.

## Why

Amazon-style stores give you seven keyword slots (50 characters each) and a
bunch of categories. Most authors either paste random guesses or pay for
mystery tools. This one keeps it honest and local:

- **Paste candidates** straight from your notes (stdin-friendly, dedupes for you).
- **Score with local heuristics** from `bookkeywordlab/defaults/rules.yaml` - no cloud, no accounts.
- **Cluster related terms** so different slots cover different search intents.
- **Flag risky words** (brand names like ChatGPT/Kindle, overpromise claims, personal data, adult terms, spammy wording) before Amazon does.
- **Draft a seven-slot plan and a category shortlist**, each with reasoning notes you can defend to future-you.
- Optionally **brainstorm** through any OpenAI-compatible endpoint (default: Ollama at `http://localhost:11434/v1`). Keyless forever - the CLI never asks for, sends, or stores an API key.

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install .            # or: pip install -e ".[dev]" for development
.venv/bin/bkwl --help
```

Or without installing: `python3 -m bookkeywordlab --help` (needs PyYAML).

## A calm little workflow

```bash
bkwl init -t "The Massive AI Manual"

# paste in: type or paste one phrase per line, end with Ctrl-D (Ctrl-Z on Windows)
bkwl add

# or straight from the command line
bkwl add "ai for beginners" "local ai basics" "plain english guide to agents"
bkwl add --as "elevator notes" -        # stdin paste, labeled with a source

bkwl list      # pasted view: quick scores, risk badges, sources
bkwl score     # explained scores, sorted best-first
bkwl cluster   # related terms grouped
bkwl risk      # only the flagged terms, with the why

bkwl plan      # the seven-slot draft + category shortlist, with reasons
bkwl export -f markdown -o keywords.md
bkwl export    # text to stdout - copy straight into the KDP forms
```

Remove anything by phrase: `bkwl remove "local ai basics"` (exact match first,
close match as backup). Start over: `bkwl reset --yes`.

## The brainstorm step (optional, keyless)

Point it at any OpenAI-compatible endpoint. Defaults to Ollama on your machine:

```bash
ollama serve                                # in another terminal, if needed
ollama pull llama3.2                        # once
bkwl models                                 # see what the endpoint offers
bkwl brainstorm -m llama3.2                 # suggestions get scored + screened
bkwl brainstorm -m llama3.2 --no-add       # look but don't add
bkwl brainstorm --base-url http://127.0.0.1:8000/v1 -m qwen2.5  # any endpoint
```

Suggestions come back scored by your rules file, screened for risk, deduped
against what you already have, and then added as normal candidates. If the
endpoint is down, the CLI tells you the likely fix and exits cleanly.

**Never a key:** `bkwl` sends `Content-Type`, `Accept`, and a `User-Agent` - no
`Authorization` header, ever. Keep the endpoint on `localhost` or your own
network and nothing about your (meta)data leaves your machine.

## How scoring works (all local, all editable)

Everything heuristic lives in one YAML rule file:

- `scoring.boosts` / `scoring.penalties` - literal or regex patterns with weights and honest reasons, e.g. `for beginners +6 (beginner-audience language is exactly who this book serves)`.
- `scoring.length` - the 2-6 word sweet spot, a won't-fit-50-chars penalty.
- `clustering` - token-overlap measure (`containment` or `jaccard`) and threshold.
- `risk.rules` - id + severity + pattern + reason: `brand-name`, `overpromise`, `privacy-or-secrets`, `adult-or-substances`, `spammy`, `vague-year`.
- `categories` - your shortlist shelves with `fit_terms` and a `weight`; the CLI scores fit against your candidates and reasons about the ranking.
- `planner` - slot count (7), slot width (50), how many primary/alternate categories to shortlist.

Customize without touching code:

```bash
cp "$(python3 -c 'import bookkeywordlab, os; print(os.path.join(os.path.dirname(bookkeywordlab.__file__), "defaults", "rules.yaml"))')" my-rules.yaml
bkwl score --rules my-rules.yaml     # same flag on any command
```

A word about brands: terms like "ChatGPT prompt secrets" and "guaranteed
bestseller" score decently and then get **excluded from slots on purpose** -
brand names don't belong in KDP keyword fields, claims get listings flagged.
Brand wording can still be fine in your title/subtitle (with care), which is
why the terms stay visible with their reasoning instead of being hidden.

## Files it touches

- `book-keyword-lab-state.json` - your candidates and book title (this folder, rename via `--state`).
- Export files you ask for (`-o`). Nothing else; no network except the optional brainstorm request you trigger.

## Development

```bash
pip install -e ".[dev]"
pytest
```

The test suite covers parsing, scoring, clustering, risk screens, the planner,
exports, storage, the keyless endpoint client (via a tiny local fake server),
and the CLI end-to-end. Design notes on known gaps live in `STATUS.md`.

## Credit and license

Book Keyword Lab is a project of **Asdale Dynamics, LLC** - the LLC behind
*The Massive AI Manual* by Dylan Asdale (registered nurse turned AI author),
which explains AI like a friend would: plain English, step by step, never
condescending. Released under the MIT License; `Copyright (c) 2026 Asdale
Dynamics, LLC`.
