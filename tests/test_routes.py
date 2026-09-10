import pytest

from app import create_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)  # force mock mode, deterministic
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    app = create_app("testing")
    # Flask/Werkzeug's test client keeps a cookie jar across requests made
    # from the same client object by default, so the session cookie set by
    # GET /api/questions is automatically sent on the following POST
    # /api/submit -- no explicit session_transaction() needed.
    return app.test_client()


def get_questions(client):
    resp = client.get("/api/questions")
    assert resp.status_code == 200
    return resp.get_json()


def full_valid_answers(questions):
    """Communication answers high (4), Problem-Solving answers low (2), so
    tests can assert a specific stronger/weaker category deterministically."""
    return {q["id"]: (4 if q["category"] == "Communication" else 2) for q in questions}


def test_get_questions_returns_8_questions_two_categories(client):
    data = get_questions(client)
    assert len(data["questions"]) == 8
    assert set(data["categories"]) == {"Communication", "Problem-Solving"}

    comm_count = sum(1 for q in data["questions"] if q["category"] == "Communication")
    prob_count = sum(1 for q in data["questions"] if q["category"] == "Problem-Solving")
    assert comm_count == 4
    assert prob_count == 4


def test_get_questions_returns_a_random_subset_of_the_pool():
    """Not a strict guarantee of randomness (that would be flaky), but
    confirms the endpoint is sampling from a larger pool rather than always
    returning the same fixed 8 -- calling it many times should surface more
    than 4 distinct Communication question ids across attempts."""
    from app import create_app

    app = create_app("testing")
    client = app.test_client()

    seen_comm_ids = set()
    for _ in range(15):
        data = client.get("/api/questions").get_json()
        seen_comm_ids.update(
            q["id"] for q in data["questions"] if q["category"] == "Communication"
        )

    assert len(seen_comm_ids) > 4


def test_submit_without_prior_get_returns_400(client):
    """Submitting cold, with no session established by a prior GET
    /api/questions, must be rejected -- there's nothing to validate against."""
    resp = client.post("/api/submit", json={"answers": {"comm_1": 4}})
    assert resp.status_code == 400
    assert "No active quiz found" in resp.get_json()["error"]


def test_submit_missing_answers_field_returns_400(client):
    get_questions(client)
    resp = client.post("/api/submit", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_submit_incomplete_answers_returns_400(client):
    data = get_questions(client)
    answers = full_valid_answers(data["questions"])
    del answers[data["questions"][0]["id"]]

    resp = client.post("/api/submit", json={"answers": answers})
    assert resp.status_code == 400
    assert "Missing answers" in resp.get_json()["error"]


def test_submit_out_of_range_answer_returns_400(client):
    data = get_questions(client)
    answers = full_valid_answers(data["questions"])
    answers[data["questions"][0]["id"]] = 9

    resp = client.post("/api/submit", json={"answers": answers})
    assert resp.status_code == 400


def test_submit_answer_for_question_outside_this_session_returns_400(client):
    """An id that's a real question in the pool, but wasn't part of THIS
    session's sampled 8, must be rejected as unknown -- proves scoring is
    scoped to what was actually shown, not the whole pool."""
    data = get_questions(client)
    answers = full_valid_answers(data["questions"])

    from app.questions import QUESTION_POOL

    shown_ids = {q["id"] for q in data["questions"]}
    not_shown = next(q for q in QUESTION_POOL if q["id"] not in shown_ids)
    answers[not_shown["id"]] = 3

    resp = client.post("/api/submit", json={"answers": answers})
    assert resp.status_code == 400
    assert "Unknown question" in resp.get_json()["error"]


def test_submit_valid_answers_returns_scores_and_insight(client):
    data = get_questions(client)
    answers = full_valid_answers(data["questions"])

    resp = client.post("/api/submit", json={"answers": answers})
    assert resp.status_code == 200

    result = resp.get_json()
    assert result["scores"]["Communication"] == 4.0
    assert result["scores"]["Problem-Solving"] == 2.0
    assert "stronger_category_sentence" in result["insight"]
    assert "improvement_suggestion" in result["insight"]


def test_index_page_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Evalix" in resp.data