from bookkeywordlab.textutil import normalize_term, split_candidates, tokenize


def test_tokenize_lowercases_and_keeps_plus():
    assert tokenize("AI for Beginners") == ["ai", "for", "beginners"]
    assert tokenize("C++ gpt-4o 2026") == ["c++", "gpt", "4o", "2026"]


def test_normalize_term_is_canonical():
    assert normalize_term("AI for  Beginners") == normalize_term("ai for beginners")
    assert normalize_term("  ChatGPT  ") == "chatgpt"


def test_split_candidates_handles_paste_shapes():
    raw = """- ai for beginners
2. plain english guide
"local ai basics";
llm basics | prompt writing, automation wins
"""
    assert split_candidates(raw) == [
        "ai for beginners",
        "plain english guide",
        "local ai basics",
        "llm basics",
        "prompt writing",
        "automation wins",
    ]


def test_split_candidates_drops_blanks():
    assert split_candidates("\n\n  ,, ;  ") == []


def test_split_candidates_keeps_normal_phrase_intact():
    assert split_candidates("ai for beginners") == ["ai for beginners"]
