"""
AI-generated insight for the quiz results.

Provider chain: Gemini (primary) -> Groq (fallback) -> mocked response.

Design notes
------------
- Gemini is tried first. If GEMINI_API_KEY isn't set, if the call raises for
  any reason (network, auth, rate limit / quota exceeded), or if the model's
  response gets cut off by the output token limit, we fall back to Groq.
- If Groq also isn't configured or also fails, we fall back to a
  deterministic mocked response so the quiz still returns a result instead
  of a 500. Every fallback is logged so it's visible in server logs.
- Both providers are asked for STRICT JSON so the response is parsed, not
  scraped out of free-form prose.
- The prompt includes the category averages AND each individual question's
  text/answer, so the model has concrete signal to point to instead of
  inventing generic advice.
"""

import json
import logging
import os

from .scoring import stronger_weaker_category

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
MAX_OUTPUT_TOKENS = 300

SYSTEM_PROMPT = """You are a concise, honest career-development coach reviewing a \
person's self-assessment quiz. You will be given their average score (1-5) in \
two skill categories, plus their individual answers within each category.

Respond with STRICT JSON only — no markdown fences, no preamble, no trailing \
text. Match exactly this schema:

{"stronger_category_sentence": "<string>", "improvement_suggestion": "<string>"}

Rules:
- stronger_category_sentence: exactly one sentence naming the stronger \
category and referencing the actual score gap between the two categories.
- improvement_suggestion: exactly one sentence with a SPECIFIC, concrete \
action for the weaker category — name a technique, a format, or an exercise. \
Do not say generic things like "practice more", "try harder", or "work on it".
- Ground the suggestion in whichever individual question(s) scored lowest, \
not just the category average.
"""


class TokenLimitExceeded(Exception):
    """Raised when a provider truncated its response at the output token limit."""


def _format_answers_for_prompt(category_scores, answers, questions):
    """Build a compact, readable block of per-question data for the prompt."""
    lines = []
    for category in category_scores:
        lines.append(f"\n{category} — average {category_scores[category]:.2f}/5")
        for q in questions:
            if q["category"] != category:
                continue
            score = answers.get(q["id"])
            lines.append(f'  - "{q["text"]}" -> {score}/5')
    return "\n".join(lines)


def build_user_prompt(category_scores, answers, questions):
    details = _format_answers_for_prompt(category_scores, answers, questions)
    return (
        "Here are this person's self-assessment results:\n"
        f"{details}\n\n"
        "Write the JSON response now."
    )


def _mock_response(category_scores):
    """
    Deterministic stand-in used when no provider is configured, or every
    configured provider fails. Clearly labelled so it's never mistaken for a
    real model response.
    """
    stronger, weaker = stronger_weaker_category(category_scores)
    gap = round(category_scores[stronger] - category_scores[weaker], 2)
    return {
        "stronger_category_sentence": (
            f"[MOCKED] {stronger} is your stronger area, scoring {gap} points "
            f"higher on average than {weaker}."
        ),
        "improvement_suggestion": (
            f"[MOCKED] For {weaker}, run a weekly 15-minute retro on one "
            f"recent example and write down exactly what you'd change next time."
        ),
    }


def _parse_and_validate(raw_text):
    data = json.loads(raw_text)  # raises json.JSONDecodeError if malformed

    if "stronger_category_sentence" not in data or "improvement_suggestion" not in data:
        raise ValueError(f"AI response missing expected keys: {data!r}")

    return {
        "stronger_category_sentence": data["stronger_category_sentence"],
        "improvement_suggestion": data["improvement_suggestion"],
    }


def _call_gemini(category_scores, answers, questions, api_key):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    user_prompt = build_user_prompt(category_scores, answers, questions)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            max_output_tokens=MAX_OUTPUT_TOKENS,
            temperature=0.4,
        ),
    )

    finish_reason = None
    if response.candidates:
        finish_reason = getattr(response.candidates[0], "finish_reason", None)
    if finish_reason is not None and "MAX_TOKENS" in str(finish_reason):
        raise TokenLimitExceeded("Gemini response was truncated at the output token limit.")

    if not response.text:
        raise ValueError("Gemini returned an empty response.")

    return _parse_and_validate(response.text.strip())


def _call_groq(category_scores, answers, questions, api_key):
    from groq import Groq

    client = Groq(api_key=api_key)
    user_prompt = build_user_prompt(category_scores, answers, questions)

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=MAX_OUTPUT_TOKENS,
        temperature=0.4,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    choice = response.choices[0]
    if choice.finish_reason == "length":
        raise TokenLimitExceeded("Groq response was truncated at the max token limit.")

    raw_text = choice.message.content
    if not raw_text:
        raise ValueError("Groq returned an empty response.")

    return _parse_and_validate(raw_text.strip())


def generate_insight(category_scores, answers, questions):
    """
    Return {"stronger_category_sentence": str, "improvement_suggestion": str}.

    Tries Gemini first, falls back to Groq on any failure (including hitting
    the token limit), and falls back to a mocked response if neither
    provider is configured or both fail — so the quiz always returns a result.
    """
    gemini_key = os.environ.get("GEMINI_API_KEY")
    groq_key = os.environ.get("GROQ_API_KEY")

    if gemini_key:
        try:
            return _call_gemini(category_scores, answers, questions, gemini_key)
        except TokenLimitExceeded:
            logger.warning("Gemini hit its output token limit — falling back to Groq.")
        except Exception:
            logger.exception("Gemini call failed — falling back to Groq.")
    else:
        logger.info("GEMINI_API_KEY not set — skipping Gemini, trying Groq.")

    if groq_key:
        try:
            return _call_groq(category_scores, answers, questions, groq_key)
        except TokenLimitExceeded:
            logger.warning("Groq hit its output token limit — falling back to mocked insight.")
        except Exception:
            logger.exception("Groq call failed — falling back to mocked insight.")
    else:
        logger.info("GROQ_API_KEY not set — skipping Groq.")

    logger.info("No AI provider produced a result — returning mocked insight.")
    return _mock_response(category_scores)