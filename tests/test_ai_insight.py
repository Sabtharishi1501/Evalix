import json
from types import SimpleNamespace
from unittest.mock import patch

from app.ai_insight import build_user_prompt, generate_insight
from app.questions import QUESTIONS

CATEGORY_SCORES = {"Communication": 4.5, "Problem-Solving": 2.25}
ANSWERS = {q["id"]: (4 if q["category"] == "Communication" else 2) for q in QUESTIONS}


def test_build_user_prompt_includes_scores_and_question_text():
    prompt = build_user_prompt(CATEGORY_SCORES, ANSWERS, QUESTIONS)
    assert "Communication" in prompt
    assert "Problem-Solving" in prompt
    assert "4.50" in prompt or "4.5" in prompt
    # A specific question's text should be present, not just the raw number
    assert QUESTIONS[0]["text"] in prompt


def test_generate_insight_uses_mock_when_no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    insight = generate_insight(CATEGORY_SCORES, ANSWERS, QUESTIONS)
    assert "[MOCKED]" in insight["stronger_category_sentence"]
    assert "[MOCKED]" in insight["improvement_suggestion"]
    assert "Communication" in insight["stronger_category_sentence"]


def _fake_anthropic_response(payload_dict):
    text_block = SimpleNamespace(type="text", text=json.dumps(payload_dict))
    return SimpleNamespace(content=[text_block])


def test_generate_insight_uses_real_call_when_key_present_and_parses_json(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")

    expected = {
        "stronger_category_sentence": "Communication is notably stronger, by 2.25 points.",
        "improvement_suggestion": "For Problem-Solving, write a one-page postmortem after your next blocked task.",
    }

    with patch("anthropic.Anthropic") as MockAnthropic:
        instance = MockAnthropic.return_value
        instance.messages.create.return_value = _fake_anthropic_response(expected)

        insight = generate_insight(CATEGORY_SCORES, ANSWERS, QUESTIONS)

    assert insight == expected


def test_generate_insight_falls_back_to_mock_on_api_error(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")

    with patch("anthropic.Anthropic") as MockAnthropic:
        instance = MockAnthropic.return_value
        instance.messages.create.side_effect = RuntimeError("network down")

        insight = generate_insight(CATEGORY_SCORES, ANSWERS, QUESTIONS)

    assert "[MOCKED]" in insight["stronger_category_sentence"]


def test_generate_insight_falls_back_to_mock_on_malformed_json(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")

    with patch("anthropic.Anthropic") as MockAnthropic:
        instance = MockAnthropic.return_value
        text_block = SimpleNamespace(type="text", text="not valid json {")
        instance.messages.create.return_value = SimpleNamespace(content=[text_block])

        insight = generate_insight(CATEGORY_SCORES, ANSWERS, QUESTIONS)

    assert "[MOCKED]" in insight["stronger_category_sentence"]