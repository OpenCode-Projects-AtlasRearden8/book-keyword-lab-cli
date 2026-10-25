from bookkeywordlab.clustering import cluster_terms, similarity
from bookkeywordlab.scoring import score_candidates


def test_containment_groups_beginner_family(default_rules):
    scored = score_candidates(
        ["ai for beginners", "artificial intelligence for beginners", "prompt writing"],
        default_rules,
    )
    clusters = cluster_terms(scored, default_rules)
    assert len(clusters) == 2  # both *_for beginners terms share 'beginners' + 'for' stopwords
    labels = {c.label for c in clusters}
    assert "prompt writing" in labels


def test_jaccard_measure_is_stricter(default_rules):
    scored = score_candidates(
        ["ai for beginners", "artificial intelligence for beginners"], default_rules
    )
    jaccard_clusters = cluster_terms(scored, default_rules, measure="jaccard")
    containment_clusters = cluster_terms(scored, default_rules, measure="containment")
    assert len(jaccard_clusters) >= len(containment_clusters)


def test_similarity_functions(default_rules):
    from bookkeywordlab.scoring import score_term

    t = score_term("ai walkthrough", default_rules).tokens
    s = score_term("ai guide", default_rules).tokens
    assert 0.0 < similarity(t, s, "containment") <= 1.0
    assert similarity(t, s, "jaccard") <= similarity(t, s, "containment")


def test_deterministic_clusters(default_rules):
    terms = [
        "ai for beginners",
        "local ai basics",
        "prompt writing",
        "prompt engineering",
        "automation wins",
    ]
    c1 = [c.label for c in cluster_terms(score_candidates(terms, default_rules), default_rules)]
    c2 = [c.label for c in cluster_terms(score_candidates(terms, default_rules), default_rules)]
    assert c1 == c2


def test_empty_input(default_rules):
    assert cluster_terms([], default_rules) == []
