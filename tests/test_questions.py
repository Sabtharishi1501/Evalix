import random

from app.questions import CATEGORIES, QUESTION_POOL, pick_random_questions


def test_pool_has_at_least_4_questions_per_category():
    for category in CATEGORIES:
        count = sum(1 for q in QUESTION_POOL if q["category"] == category)
        assert count >= 4


def test_pick_random_questions_returns_4_per_category_by_default():
    selected = pick_random_questions(rng=random.Random(1))
    for category in CATEGORIES:
        count = sum(1 for q in selected if q["category"] == category)
        assert count == 4


def test_pick_random_questions_returns_only_valid_pool_ids():
    pool_ids = {q["id"] for q in QUESTION_POOL}
    selected = pick_random_questions(rng=random.Random(2))
    assert all(q["id"] in pool_ids for q in selected)


def test_pick_random_questions_never_repeats_a_question_within_a_category():
    selected = pick_random_questions(rng=random.Random(3))
    ids = [q["id"] for q in selected]
    assert len(ids) == len(set(ids))


def test_pick_random_questions_is_deterministic_with_a_seeded_rng():
    first = pick_random_questions(rng=random.Random(42))
    second = pick_random_questions(rng=random.Random(42))
    assert [q["id"] for q in first] == [q["id"] for q in second]


def test_pick_random_questions_varies_across_different_seeds():
    """Not guaranteed mathematically for any two seeds, but with an 8-choose-4
    pool per category this is overwhelmingly likely to differ and catches a
    regression to a hardcoded/non-random selection."""
    results = {
        tuple(q["id"] for q in pick_random_questions(rng=random.Random(seed)))
        for seed in range(10)
    }
    assert len(results) > 1


def test_pick_random_questions_respects_custom_n_per_category():
    selected = pick_random_questions(n_per_category=2, rng=random.Random(4))
    for category in CATEGORIES:
        count = sum(1 for q in selected if q["category"] == category)
        assert count == 2