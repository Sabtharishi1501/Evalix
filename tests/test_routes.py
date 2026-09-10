import pytest

from app import create_app
from app.questions import QUESTIONS


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # force mock mode, deterministic
    app = create_app("testing")
    return app.test_client()


def full_valid_answers():
    return {q["id"]: (4 if q["category"] == "Communication" else 2) for q in QUESTIONS}


def test_get_questions_returns_8_questions_two_categories(client):
    resp = client.get("/api/questions")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["questions"]) == 8
    assert set(data["categories"]) == {"Communication", "Problem-Solving"}


def test_submit_missing_answers_field_returns_400(client):
    resp = client.post("/api/submit", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_submit_incomplete_answers_returns_400(client):
    answers = full_valid_answers()
    del answers[QUESTIONS[0]["id"]]
    resp = client.post("/api/submit", json={"answers": answers})
    assert resp.status_code == 400
    assert "Missing answers" in resp.get_json()["error"]


def test_submit_out_of_range_answer_returns_400(client):
    answers = full_valid_answers()
    answers[QUESTIONS[0]["id"]] = 9
    resp = client.post("/api/submit", json={"answers": answers})
    assert resp.status_code == 400


def test_submit_valid_answers_returns_scores_and_insight(client):
    answers = full_valid_answers()
    resp = client.post("/api/submit", json={"answers": answers})
    assert resp.status_code == 200

    data = resp.get_json()
    assert data["scores"]["Communication"] == 4.0
    assert data["scores"]["Problem-Solving"] == 2.0
    assert "stronger_category_sentence" in data["insight"]
    assert "improvement_suggestion" in data["insight"]


def test_index_page_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Evalix" in resp.data