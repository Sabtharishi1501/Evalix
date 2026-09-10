"""
Scoring logic for the self-assessment quiz.

Kept dependency-free and framework-agnostic on purpose: these functions don't
know about Flask, HTTP, or the AI provider. That makes them trivial to unit
test and safe to reuse (e.g. from a CLI or a batch job) later.
"""

from collections import defaultdict

MIN_SCALE = 1
MAX_SCALE = 5

TIER_STRONG = "Strong"
TIER_AVERAGE = "Average"
TIER_NEEDS_IMPROVEMENT = "Needs Improvement"

STRONG_THRESHOLD = 4.0 
AVERAGE_THRESHOLD = 3.0  

def classify_tier(score):
    """
    Return one of TIER_STRONG / TIER_AVERAGE / TIER_NEEDS_IMPROVEMENT for a
    single category's average score (1-5 scale).
    """
    if score >= STRONG_THRESHOLD:
        return TIER_STRONG
    if score >= AVERAGE_THRESHOLD:
        return TIER_AVERAGE
    return TIER_NEEDS_IMPROVEMENT


def validate_answers(answers, questions):
    """
    Raise ValueError with a human-readable message if `answers` is not a
    complete, well-formed response to `questions`.

    answers:   dict[str question_id -> int score]
    questions: list of question dicts (as in questions.QUESTIONS)
    """
    if not isinstance(answers, dict):
        raise ValueError("answers must be an object mapping question id -> score")

    expected_ids = {q["id"] for q in questions}
    received_ids = set(answers.keys())

    missing = expected_ids - received_ids
    if missing:
        raise ValueError(f"Missing answers for question(s): {', '.join(sorted(missing))}")

    unknown = received_ids - expected_ids
    if unknown:
        raise ValueError(f"Unknown question id(s): {', '.join(sorted(unknown))}")

    for qid, value in answers.items():
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"Answer for '{qid}' must be an integer, got {value!r}")
        if not (MIN_SCALE <= value <= MAX_SCALE):
            raise ValueError(
                f"Answer for '{qid}' must be between {MIN_SCALE} and {MAX_SCALE}, got {value}"
            )


def calculate_scores(answers, questions):
    """
    Return {category: average_score} rounded to 2 decimal places.

    Assumes `answers` has already been validated with validate_answers().
    """
    sums = defaultdict(float)
    counts = defaultdict(int)

    for question in questions:
        qid = question["id"]
        if qid not in answers:
            continue
        sums[question["category"]] += answers[qid]
        counts[question["category"]] += 1

    return {
        category: round(sums[category] / counts[category], 2)
        for category in sums
        if counts[category] > 0
    }


def calculate_tiers(category_scores):
    """
    Return {category: tier_label} for every category in category_scores,
    using classify_tier() on each category's average independently.
    """
    return {category: classify_tier(score) for category, score in category_scores.items()}


def stronger_weaker_category(category_scores):
    """
    Return (stronger_category, weaker_category) given a {category: score} dict.

    Ties resolve by keeping dict insertion order (first key wins as "stronger").
    Requires at least 2 categories.
    """
    if len(category_scores) < 2:
        raise ValueError("Need at least 2 categories to compare")

    ranked = sorted(category_scores.items(), key=lambda kv: kv[1], reverse=True)
    stronger = ranked[0][0]
    weaker = ranked[-1][0]
    return stronger, weaker