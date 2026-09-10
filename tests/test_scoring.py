import pytest

from app.questions import QUESTIONS
from app.scoring import calculate_scores, stronger_weaker_category, validate_answers


def make_full_answers(comm_value=4, prob_value=2):
    answers = {}
    for q in QUESTIONS:
        answers[q["id"]] = comm_value if q["category"] == "Communication" else prob_value
    return answers


def test_calculate_scores_averages_per_category():
    answers = make_full_answers(comm_value=4, prob_value=2)
    scores = calculate_scores(answers, QUESTIONS)
    assert scores["Communication"] == 4.0
    assert scores["Problem-Solving"] == 2.0


def test_calculate_scores_rounds_to_two_decimals():
    answers = make_full_answers()
    comm_ids = [q["id"] for q in QUESTIONS if q["category"] == "Communication"]
    answers[comm_ids[0]] = 5
    answers[comm_ids[1]] = 5
    answers[comm_ids[2]] = 5
    answers[comm_ids[3]] = 4
    scores = calculate_scores(answers, QUESTIONS)
    assert scores["Communication"] == 4.75


def test_validate_answers_rejects_missing_question():
    answers = make_full_answers()
    del answers[QUESTIONS[0]["id"]]
    with pytest.raises(ValueError, match="Missing answers"):
        validate_answers(answers, QUESTIONS)


def test_validate_answers_rejects_out_of_range():
    answers = make_full_answers()
    answers[QUESTIONS[0]["id"]] = 6
    with pytest.raises(ValueError, match="between 1 and 5"):
        validate_answers(answers, QUESTIONS)


def test_validate_answers_rejects_non_integer():
    answers = make_full_answers()
    answers[QUESTIONS[0]["id"]] = "strongly agree"
    with pytest.raises(ValueError, match="must be an integer"):
        validate_answers(answers, QUESTIONS)


def test_validate_answers_rejects_unknown_question_id():
    answers = make_full_answers()
    answers["not_a_real_question"] = 3
    with pytest.raises(ValueError, match="Unknown question"):
        validate_answers(answers, QUESTIONS)


def test_validate_answers_accepts_well_formed_input():
    answers = make_full_answers()
    validate_answers(answers, QUESTIONS)


def test_stronger_weaker_category():
    scores = {"Communication": 4.5, "Problem-Solving": 2.25}
    stronger, weaker = stronger_weaker_category(scores)
    assert stronger == "Communication"
    assert weaker == "Problem-Solving"


def test_stronger_weaker_category_requires_two_categories():
    with pytest.raises(ValueError):
        stronger_weaker_category({"Communication": 4.0})