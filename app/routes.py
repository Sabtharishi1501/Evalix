import logging

from flask import Blueprint, jsonify, request, session

from .ai_insight import generate_insight
from .questions import CATEGORIES, QUESTIONS_BY_ID, pick_random_questions
from .scoring import calculate_scores, validate_answers

logger = logging.getLogger(__name__)

bp = Blueprint("api", __name__, url_prefix="/api")

SESSION_KEY = "quiz_question_ids"


@bp.get("/questions")
def get_questions():
    """
    Randomly sample 4 questions per category from the pool and remember the
    exact set shown in the signed session cookie, so /api/submit can later
    validate answers against precisely what this user was actually asked --
    not the full question pool, and not a client-supplied list.
    """
    selected = pick_random_questions()
    session[SESSION_KEY] = [q["id"] for q in selected]

    return jsonify({"categories": CATEGORIES, "questions": selected})


@bp.post("/submit")
def submit():
    payload = request.get_json(silent=True)

    if payload is None or "answers" not in payload:
        return jsonify({"error": "Request body must be JSON with an 'answers' field."}), 400

    answers = payload["answers"]

    selected_ids = session.get(SESSION_KEY)
    if not selected_ids:
        return jsonify({
            "error": "No active quiz found for this session. "
                     "Please reload the page to start a new quiz."
        }), 400

    questions = [QUESTIONS_BY_ID[qid] for qid in selected_ids]

    try:
        validate_answers(answers, questions)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    scores = calculate_scores(answers, questions)

    try:
        insight = generate_insight(scores, answers, questions)
    except Exception:
        logger.exception("Unexpected failure generating AI insight.")
        insight = {
            "stronger_category_sentence": "We couldn't generate an insight this time.",
            "improvement_suggestion": "Please try submitting again in a moment.",
        }

    return jsonify({"scores": scores, "insight": insight})