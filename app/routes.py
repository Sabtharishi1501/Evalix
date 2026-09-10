import logging

from flask import Blueprint, jsonify, request

from .ai_insight import generate_insight
from .questions import CATEGORIES, QUESTIONS
from .scoring import calculate_scores, validate_answers

logger = logging.getLogger(__name__)

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/questions")
def get_questions():
    return jsonify({"categories": CATEGORIES, "questions": QUESTIONS})


@bp.post("/submit")
def submit():
    payload = request.get_json(silent=True)

    if payload is None or "answers" not in payload:
        return jsonify({"error": "Request body must be JSON with an 'answers' field."}), 400

    answers = payload["answers"]

    try:
        validate_answers(answers, QUESTIONS)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    scores = calculate_scores(answers, QUESTIONS)

    try:
        insight = generate_insight(scores, answers, QUESTIONS)
    except Exception:
        # generate_insight already falls back to a mock internally; this is a
        # last-resort guard so a truly unexpected error still returns scores
        # to the user instead of a bare 500.
        logger.exception("Unexpected failure generating AI insight.")
        insight = {
            "stronger_category_sentence": "We couldn't generate an insight this time.",
            "improvement_suggestion": "Please try submitting again in a moment.",
        }

    return jsonify({"scores": scores, "insight": insight})