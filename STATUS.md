# STATUS.md — Book Keyword Lab (bkwl)

Updated: 2026-10-25
Maintained by Asdale Dynamics, LLC.

## What was built

`bkwl` — a local-first author CLI for choosing book keywords and categories:

- **Paste candidates**: `bkwl add` reads pasted lines/commas/pipes from stdin (Ctrl-D to end) or accepts phrases as arguments; de-duplicates case/spacing-insensitively, labels sources, stores everything in a local JSON state file (`book-keyword-lab-state.json`, override with `--state`).
- **Score with local rule-file heuristics**: `bkwl score` — rules live in `bookkeywordlab/defaults/rules.yaml` (editable, load any copy with `--rules`): boosts/penalties with weights and plain reasons, word-count sweet spot, 50-char slot-fit penalty, clamped 0–100.
- **Cluster related terms**: `bkwl cluster` — greedy token-overlap clustering (containment default, Jaccard optional, threshold configurable in the rules file).
- **Flag risky words**: `bkwl risk` — screens for brand names (ChatGPT/Kindle/GitHub/…), overpromise claims (guaranteed/bestseller/cure…), personal data and API keys, adult/substance terms, spammy wording, date-stamping. High-risk terms are excluded from slots by the planner with reasons.
- **Seven-keyword slot plan + category shortlist**: `bkwl plan` — one phrase per cluster first (maximizes distinct search intents), backfill by freshest words, slots sorted by score, each with reasoning notes (cluster, score, shared/fresh words, cautions); category picks come from fit_terms in the rules file with primary/alternate marks and a "why".
- **Copy-paste export**: `bkwl export -f text|markdown|json [-o FILE]` — the text render is shaped for pasting straight into KDP forms; skipped candidates and reasoning included.
- **Optional keyless brainstorm**: `bkwl brainstorm [--base-url …] [-m model]` against any OpenAI-compatible endpoint (default Ollama `http://localhost:11434/v1`); `bkwl models` lists models. No `Authorization` header is ever sent; nothing asks for a key. Unreachable endpoints fail with a friendly hint.
- Plus: `init`, `list`, `remove`, `reset`, `--version`; deterministic output everywhere.

## How to run it

```bash
python3 -m venv .venv
.venv/bin/pip install .           # dev: pip install -e ".[dev]"
.venv/bin/bkwl --help
```

Typical session:

```bash
bkwl init -t "The Massive AI Manual"
bkwl add                          # paste lines, end with Ctrl-D / Ctrl-Z
bkwl score && bkwl cluster && bkwl risk
bkwl plan
bkwl export -f markdown -o keywords.md
```

## Verification results (this folder, 2026-10-25)

- `.venv` created; `pip install -e ".[dev]"` → OK (PyYAML 6.0.3, pytest 9.1.1).
- `bkwl --version` and `python -m bookkeywordlab --version` → `bkwl 1.0.0`.
- `pytest` → **72 passed** (parsing, rules loading, scoring, risk, clustering, planner, exports, storage, keyless endpoint client via a local fake OpenAI-compatible server, CLI end-to-end incl. stdin paste and brainstorm flows).
- `python -m compileall bookkeywordlab tests` → clean.
- Full session exercised in a fresh empty directory (init → pasted 8 terms → score → cluster → risk → plan → export text/markdown/json): risky terms (`guaranteed bestseller`, `chatgpt prompt secrets`) were excluded from slots and shown under "SKIPPED CANDIDATES" with reasons; 6 slots filled with one slot left open; category shortlist reasoned. Default state filename verified.
- Failure paths verified: missing/invalid rules file → `error:` + exit 1; corrupt state file → friendly recovery hint; unreachable endpoint → hint (suggests `ollama serve`) + exit 1.
- Brainstorm against a live Ollama was not possible in this environment (none running); the HTTP client is covered by tests against a local fake endpoint, and the real-world failure path was exercised manually (see above).

## Known gaps

- Scores are opinion-based heuristics from the rules file — there is **no live search-volume or competitor data** (and no scraping); pair with the buyer-facing numbers Amazon shows you.
- Category names in the default rules are a shortlist to verify in the live KDP category picker; Amazon renames shelves occasionally.
- Clustering is token-overlap only (no embeddings, no stemming); near-synonyms ("beginner" vs "newbie") won't cluster unless they share tokens.
- Brainstorm quality depends entirely on the local model you point at; the CLI screens and scores everything it receives.
- The seven slots avoid repeated phrases across slots and warn on shared words, but KDP's own "don't repeat" guidance evolves — review the export before submitting.
- English-only tokenization (`[a-z0-9#+]`); no CJK/accented collapsing.
- No clipboard integration by design — copy from stdout or the export file to stay secretless and dependency-free.

## Safety & privacy

No secrets, API keys, or personal data are stored, sent, or committed: state and exports are local files; brainstorm requests carry no Authorization header; the test-suite's fake endpoint lives on loopback.
