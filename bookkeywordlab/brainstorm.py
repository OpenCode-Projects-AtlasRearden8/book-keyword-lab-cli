"""Optional brainstorm step: ask a friendly, OpenAI-compatible endpoint for ideas.

Keyless by design - the default target is Ollama on your own machine
(http://localhost:11434/v1), and any other *base_url* works. We never ask for,
send, or store an API key.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Dict, List, Optional

from .textutil import normalize_term, tokenize
from . import __version__

DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "llama3.2"
DEFAULT_TIMEOUT = 90.0
USER_AGENT = f"book-keyword-lab/{__version__}"


class BrainstormError(RuntimeError):
    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.hint = hint


def _post_chat(base_url: str, model: str, messages: List[Dict[str, str]], timeout: float) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": messages,
        "temperature": 0.6,
        "stream": False,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )  # deliberately no Authorization header: brainstorm is keyless
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:300]
        except Exception:  # pragma: no cover
            pass
        raise BrainstormError(
            f"endpoint returned HTTP {exc.code} for {url}",
            hint=detail or "check the model name with: bkwl models",
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise BrainstormError(
            f"could not reach {url} ({exc})",
            hint=(
                "is the model server running? for the default Ollama endpoint try "
                "`ollama serve` (or `ollama pull llama3.2` first); point --base-url at any "
                "OpenAI-compatible server"
            ),
        ) from exc

    choices = payload.get("choices") or []
    if not choices:
        raise BrainstormError(f"no choices in the response from {url}", hint="try another model")
    try:
        content = choices[0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise BrainstormError(f"unexpected response shape from {url}") from exc
    if not content.strip():
        raise BrainstormError(
            f"the model at {url} returned an empty completion",
            hint="try another model or re-run - local models are happily imprecise",
        )
    return content


def extract_phrases(content: str, limit: int = 16) -> List[str]:
    """Pull keyword phrases out of a completion: JSON array first, bullets as backup."""
    phrases: List[str] = []

    def accept(item) -> None:
        if not isinstance(item, str):
            return
        s = item.strip().strip("\"'").strip()
        s = re.sub(r"^\s*(?:[-\*\u2022#>]|\d+[.)])\s+", "", s).strip()
        if not s:
            return
        words = tokenize(s)
        if not words or len(words) > 8 or len(s) > 64:
            return
        phrases.append(s)

    match = re.search(r"\[.*\]", content, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, list):
                for item in data:
                    accept(item)
        except ValueError:
            pass

    if not phrases:
        for line in content.splitlines():
            for part in line.split(","):
                accept(part)

    final: List[str] = []
    seen: set = set()
    for p in phrases:
        key = normalize_term(p)
        if key and key not in seen:
            seen.add(key)
            final.append(p)
    return final[:limit]


def brainstorm(
    theme: str,
    seed_terms: Optional[List[str]] = None,
    *,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    timeout: float = DEFAULT_TIMEOUT,
    count: int = 12,
) -> List[str]:
    seed_terms = seed_terms or []
    brief = (
        "Suggest short keyword phrases (2-6 words each) that real readers might type "
        "when searching for this book. Rules: no brand names or trademarks; no hype or "
        "medical claims; no repetition of the existing list below; plain, warm language."
        f"{' Avoid repeating these existing terms: ' + '; '.join(seed_terms[:25]) + '.' if seed_terms else ''}"
        f" Return ONLY a JSON array of exactly {count} distinct phrases."
    )
    content = _post_chat(
        base_url,
        model,
        messages=[
            {"role": "system", "content": "You are a careful, honest publishing assistant."},
            {"role": "user", "content": f"Book theme: {theme}\n\n{brief}"},
        ],
        timeout=timeout,
    )
    phrases = extract_phrases(content, limit=max(count, 16))
    return phrases


def list_models(base_url: str, timeout: float = 20.0) -> List[str]:
    url = base_url.rstrip("/") + "/models"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        method="GET",
    )  # no Authorization header ever
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        raise BrainstormError(f"endpoint returned HTTP {exc.code} for {url}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise BrainstormError(
            f"could not reach {url} ({exc})",
            hint=(
                "is the model server running? for the default Ollama endpoint try "
                "`ollama serve`; point --base-url at any OpenAI-compatible server"
            ),
        ) from exc
    data = payload.get("data") if isinstance(payload, dict) else payload
    ids: List[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("id"):
                ids.append(str(item["id"]))
            elif isinstance(item, str):
                ids.append(item)
    return sorted(set(ids))
