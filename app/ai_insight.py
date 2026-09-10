"""
AI-generated insight for the quiz results.

Provider chain: Gemini (primary) -> Groq (fallback) -> mocked response.
"""

import json
import logging
import os

from .scoring import classify_tier, stronger_weaker_category
from .scoring import TIER_STRONG, TIER_AVERAGE, TIER_NEEDS_IMPROVEMENT

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")

MAX_OUTPUT_TOKENS = 800

SYSTEM_PROMPT = """You are a concise, honest career-development coach reviewing a \
person's self-assessment quiz. You will be given their average score (1-5) in \
two skill categories, a tier label for each category, and their individual \
answers within each category.

Tier definitions (based on the category's own average, not a comparison \
between categories):
- "Strong": average score of 4.0 or higher.
- "Average": average score from 3.0 up to (but not including) 4.0.
- "Needs Improvement": average score below 3.0.

Respond with STRICT JSON only — no markdown fences, no preamble, no trailing \
text. Match exactly this schema:

{"stronger_category_sentence": "<string>", "improvement_suggestion": "<string>"}

Rules:
- Use the tier definitions above ONLY to decide how positive, neutral, or \
urgent your tone should be for each category. NEVER write the literal tier \
label words ("Strong", "Average", "Needs Improvement", "tier", etc.) in \
either output string -- describe the person's actual standing in plain, \
natural language instead.
- stronger_category_sentence: exactly one sentence that describes BOTH \
categories in language that matches their real standing (a category with a \
high average should be praised as a genuine strength; a mid-range average \
should read as solid with room to grow, NOT as a weakness just because it's \
lower than the other category; a low average should be named plainly, in \
your own words, as something that needs real, focused work). Do not imply a \
category needs work just because it scored lower than the other one if its \
own average is solid or high -- judge each category on its own standing, \
not only on the gap between them.
- improvement_suggestion: exactly one sentence with a SPECIFIC, concrete \
action for whichever category has the weaker real standing (or, if both \
categories are equally weak, whichever has the lower average) — name a \
technique, a format, or an exercise. Do not say generic things like \
"practice more", "try harder", or "work on it". If that category's average \
is already high, instead give a stretch suggestion to push it further, \
since it does not need basic improvement.
- Ground the suggestion in whichever individual question(s) scored lowest \
within that category, not just the category average.
"""


class TokenLimitExceeded(Exception):
    """Raised when a provider truncated its response at the output token limit."""


def _format_answers_for_prompt(category_scores, answers, questions):
    """Build a compact, readable block of per-question data for the prompt."""
    lines = []
    for category in category_scores:
        tier = classify_tier(category_scores[category])
        lines.append(f"\n{category} — average {category_scores[category]:.2f}/5 (tier: {tier})")
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


_TIER_STRONG_PHRASES = {
    TIER_STRONG: "a genuine strength",
    TIER_AVERAGE: "solid, with room to grow",
    TIER_NEEDS_IMPROVEMENT: "an area that needs real work",
}

_TIER_SUGGESTION_TEMPLATES = {
    TIER_NEEDS_IMPROVEMENT: (
        "[MOCKED] For {weaker}, run a weekly 15-minute retro on one recent "
        "example and write down exactly what you'd change next time."
    ),
    TIER_AVERAGE: (
        "[MOCKED] For {weaker}, pick one recent example each week and ask a "
        "peer for specific feedback on what would have made it stronger."
    ),
    TIER_STRONG: (
        "[MOCKED] {weaker} is already strong, so stretch it further by "
        "mentoring someone else through a real example this month."
    ),
}


def _mock_response(category_scores):
    """
    Deterministic stand-in used when no provider is configured, or every
    configured provider fails. Clearly labelled so it's never mistaken for a
    real model response. Reflects each category's own tier, not just which
    one is relatively higher.
    """
    stronger, weaker = stronger_weaker_category(category_scores)
    stronger_tier = classify_tier(category_scores[stronger])
    weaker_tier = classify_tier(category_scores[weaker])
    gap = round(category_scores[stronger] - category_scores[weaker], 2)

    stronger_phrase = _TIER_STRONG_PHRASES[stronger_tier]
    weaker_phrase = _TIER_STRONG_PHRASES[weaker_tier]

    suggestion_template = _TIER_SUGGESTION_TEMPLATES[weaker_tier]

    return {
        "stronger_category_sentence": (
            f"[MOCKED] {stronger} is {stronger_phrase} (scoring "
            f"{category_scores[stronger]:.2f}/5), while {weaker} is "
            f"{weaker_phrase} (scoring {category_scores[weaker]:.2f}/5), a "
            f"gap of {gap} points."
        ),
        "improvement_suggestion": suggestion_template.format(weaker=weaker),
    }


def _parse_and_validate(raw_text):
    data = json.loads(raw_text)

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
            thinking_config=types.ThinkingConfig(thinking_level="low"),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
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
        reasoning_effort="low",
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