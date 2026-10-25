import json

import pytest

from bookkeywordlab.brainstorm import (
    BrainstormError,
    brainstorm,
    extract_phrases,
    list_models,
)


def test_extract_phrases_from_json_array():
    content = 'Here you go: ["ai for beginners", "local basics", "this one is far too long to be a keyword phrase at all"]'
    phrases = extract_phrases(content)
    assert phrases == ["ai for beginners", "local basics"]


def test_extract_phrases_from_bullets_fallback():
    content = "1. ai for beginners\n- local ai basics\n3) plain english guide, prompt start\n"
    phrases = extract_phrases(content)
    assert "ai for beginners" in phrases
    assert "local ai basics" in phrases
    assert "plain english guide" in phrases
    assert "prompt start" in phrases


def test_extract_phrases_dedupes_and_blocks_overlong():
    content = json.dumps(
        ["AI For Beginners", "ai for beginners", "a phrase " + "that " * 12 + "goes long"]
    )
    phrases = extract_phrases(content)
    assert phrases == ["AI For Beginners"]


def test_brainstorm_via_fake_endpoint(endpoint_factory):
    handle = endpoint_factory(
        content=["ai for beginners", "plain english guide", "guaranteed bestseller"]
    )
    phrases = brainstorm(
        "beginner AI book",
        base_url=handle.base_url,
        model="test-model",
        timeout=10,
    )
    assert phrases == ["ai for beginners", "plain english guide", "guaranteed bestseller"]
    body = handle.holder.last_body
    assert body["model"] == "test-model"
    assert "messages" in body
    headers = handle.holder.last_headers
    assert "Authorization" not in {k.title(): v for k, v in headers.items()}


def test_models_listing(endpoint_factory):
    handle = endpoint_factory(model_ids=["mistral", "llama3.2", "mistral"])
    models = list_models(handle.base_url)
    assert models == ["llama3.2", "mistral", "mistral"][:2]


def test_unreachable_endpoint_raises_with_hint():
    with pytest.raises(BrainstormError) as err:
        brainstorm("theme", base_url="http://127.0.0.1:9/v1", timeout=5)
    assert "could not reach" in str(err.value)
    assert err.value.hint


def test_seed_terms_are_passed_into_the_prompt(endpoint_factory):
    handle = endpoint_factory(content=["x"])
    brainstorm(
        "theme",
        seed_terms=["existing phrase"],
        base_url=handle.base_url,
        model="m",
        timeout=10,
    )
    sent = str(handle.holder.last_body)
    assert "existing phrase" in sent
