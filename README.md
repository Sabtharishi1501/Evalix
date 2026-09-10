# Evalix

A short, two-category self-assessment quiz that scores your answers and uses
an AI provider to generate one honest, specific insight: which category you're
stronger in, and one concrete way to improve the weaker one.

Built with Flask (app-factory pattern), a Gemini → Groq → mocked-response
provider chain for the AI call, and a static (no build step) HTML/CSS/JS
frontend.

---

## Quick start

```bash
# 1. Clone and enter the project
git clone <your-repo-url>
cd Evalix

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
copy .env.example .env       # Windows
cp .env.example .env         # macOS/Linux
# Edit .env and add a GEMINI_API_KEY and/or GROQ_API_KEY if you have one.
# If you leave both blank, the app still runs — it returns a clearly
# labeled [MOCKED] insight instead of calling a real AI API.

# 5. Run the dev server
python app.py
# -> http://localhost:5000

# 6. Run the tests
pytest -v
```

---

## Project structure

```
Evalix/
├── app/
│   ├── __init__.py       # App factory: creates Flask app, wires up static
│   │                        file serving, blueprint, error handlers, rate limiter
│   ├── config.py           # Dev/Testing/Production config classes
│   ├── questions.py        # The 8 questions + 2 categories (single source of truth)
│   ├── scoring.py           # Pure functions: validate answers, average per
│   │                          category, determine stronger/weaker category
│   ├── ai_insight.py         # Prompt construction + Gemini/Groq/mock provider chain
│   └── routes.py              # GET /api/questions, POST /api/submit
├── static/
│   ├── index.html               # Single page: sectioned quiz view + results view
│   ├── app.js                     # Fetches questions, tracks answers per section, renders results
│   └── style.css                    # Styling
├── tests/
│   ├── test_scoring.py                 # Unit tests for scoring.py
│   ├── test_ai_insight.py                # Unit tests for the provider chain (mocked)
│   └── test_routes.py                      # Integration tests via Flask's test client
    └── test_questions.py
├── app.py                                    # Dev entry point (python app.py)
├── requirements.txt
├── .env.example
└── README.md
```

---

## How it works

**Quiz (Part 1).** `app/questions.py` defines 8 questions split evenly across
two categories, Communication and Problem-Solving. The frontend fetches this
from `GET /api/questions` (so the question data lives in exactly one place —
the frontend never hardcodes questions) and renders it as a short, sectioned
flow: one category's 4 questions per screen, with a "Section X of Y" label.
The Next button for a section stays disabled until every question in that
section is answered; the final section shows a Submit button instead of
Next. Answers accumulate across sections in `app.js`'s `state.answers` as
the person moves through the quiz, so by the time they reach Submit on the
last section, the full answer set for all categories is ready to send. On
submit, `POST /api/submit` validates the answers, averages each category
with `scoring.calculate_scores`, and returns both the scores and the AI
insight in one response.

**AI insight (Part 2).** `app/ai_insight.py` builds a prompt from the category
averages *and* every individual question/answer pair — not just the two
averages — so the model has something concrete to point to instead of
inventing generic advice. Each category's average is also classified into a
tier (Strong / Average / Needs Improvement, via `scoring.classify_tier`) so
the model judges each category on its own standing, not only on the gap
between the two — a solid 4.2 shouldn't get flagged as "needing work" just
because the other category scored higher. The system prompt requires strict
JSON output, forbids phrases like "practice more," and forbids writing the
literal tier label words in the output (the tier only shapes tone/severity,
never appears verbatim). The call chain is:

1. **Gemini**, if `GEMINI_API_KEY` is set.
2. **Groq**, if Gemini's key is missing, the call fails for any reason
   (network, auth, quota), or the response is truncated by the output token
   limit.
3. A **deterministic mocked response**, clearly labeled `[MOCKED]` both in
   the JSON payload and in the UI, if neither provider is configured or both
   fail. This means the app always returns a usable result and the real
   integration path (prompt building, request shape, response parsing) is
   exercised and tested even without live credentials.

### Example prompt (system message)

> You are a concise, honest career-development coach reviewing a person's
> self-assessment quiz. You will be given their average score (1-5) in two
> skill categories, a tier label for each category, and their individual
> answers within each category. Respond with STRICT JSON only... Rules: use
> the tier definitions only to decide tone, never write the literal tier
> label words; improvement_suggestion must name a specific technique,
> format, or exercise for the weaker category and must not say generic
> things like "practice more."

---

## What I skipped, and why

- **No database.** Not required by the brief; quiz state lives entirely in
  browser memory for the duration of one session.
- **No CI pipeline.** Given more time I'd add a GitHub Actions workflow
  running `pytest` on every push — straightforward, just cut for time.
- **No production WSGI entry point.** The app runs via `python app.py` for
  development. A `wsgi.py` + gunicorn setup would be the natural next step
  before a real deployment, but it's cut from this submission since it
  wasn't required by the brief.
- **No live integration test against the real Gemini/Groq APIs.** The test
  suite mocks both providers so it's deterministic and doesn't burn API
  quota on every run. I manually verified the real call paths once against
  live keys during development instead of baking that into the automated
  suite.
- **No second-pass quality check on the AI's output** (see Part 3, Q2) —
  right now a response can be structurally valid JSON but still vague, and
  nothing catches that automatically yet.
- **In-memory rate limiting** (Flask-Limiter's default storage) — fine for a
  single dev/demo process, but doesn't coordinate across multiple gunicorn
  workers or multiple instances. Flagged in code comments and in Part 3, Q1.

---

## Part 3 — Written answers

### 1. What would break first at 1,000 concurrent users, and what's the smallest fix?

The first thing to fall over is almost certainly **the AI call blocking a
whole gunicorn worker for its full duration**. Gunicorn's default sync
worker handles one request at a time; a Gemini or Groq call can easily take
1-3+ seconds. With a handful of workers, a burst of concurrent `/api/submit`
requests queues up fast and users start seeing timeouts, even though the
actual CPU work (scoring, JSON parsing) is trivial — the bottleneck is
workers sitting idle waiting on a network response.

The smallest fix is a **config change, not a code change**: switch gunicorn
to a worker class built for blocking I/O (`gevent` or `gthread`) and raise
the worker/thread count, e.g. `gunicorn -k gthread -w 4 --threads 8 -b
0.0.0.0:8000 <entry_module>:app` (once a WSGI entry point exists). That lets
each process hold many in-flight AI calls instead of one, with no
application code touched.

The second thing to break, slightly after that, is the **in-memory rate
limiter** — its counters live per-process, so with multiple workers the
effective limit is `configured_limit × worker_count`, and it resets on every
restart. At real scale I'd move it to a shared store (Redis, which
Flask-Limiter supports natively via a one-line storage URI change) so limits
are enforced consistently across all workers and instances.

### 2. The AI response sometimes comes back vague. How would you notice, and what would you do?

Right now the only validation is *structural* — the JSON has the two
expected keys — not *qualitative*. A response like `"improvement_suggestion":
"Just keep practicing your communication skills"` would sail through
unnoticed even though it's exactly the kind of generic advice the prompt
tries to forbid.

To notice it, I'd log every raw AI response (already logged on failure, I'd
extend this to log on success too, at debug level) and add a lightweight
automated heuristic right after parsing: reject the response if
`improvement_suggestion` matches a small blocklist of generic phrases
("practice more," "try harder," "work on it," "stay positive") or falls
under a minimum length/specificity threshold. On day one that's cheap
pattern matching, not another model call.

What to do about it: if the heuristic flags a response, retry once with a
slightly stronger instruction ("your previous answer was too generic, name
an actual named technique or exercise") before falling back to the mocked
response — so a single vague reply doesn't just get silently accepted, but a
persistently uncooperative model still degrades gracefully instead of
erroring. Longer term, I'd add a lightweight thumbs-up/down on the insight
in the UI, logged with the prompt and response, to build a real dataset of
what "vague" looks like in practice rather than guessing at a blocklist.

### 3. With one more day, what's the single thing you'd build or fix next, and why?

The quality-check-and-retry loop described in Q2. The core value of this app
*is* the specificity of the AI insight — the brief is explicit that generic
advice is a failure case — so a heuristic that catches and retries vague
responses improves the thing users actually experience, more than any
infrastructure change would. Scaling and rate-limiting problems (Q1) only
matter once the app has real traffic; output quality matters on the very
first submission. If I had a full extra day I'd build the blocklist +
retry-once logic, add the success-path logging needed to see how often it
actually triggers, and use that data to tighten the prompt further.