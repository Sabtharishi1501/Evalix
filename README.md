# Evalix

A short, two-category self-assessment quiz that scores your answers and uses
an AI provider to generate one honest, specific insight: which category
you're stronger in, and one concrete way to improve the weaker one.

This README follows the structure of the assignment brief directly, so each
section below maps to Part 1 / Part 2 / Part 3 as given. 

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
# labeled [MOCKED] insight instead of calling a real AI API (see Part 2).

# 5. Run the dev server
python app.py
# -> http://localhost:5000
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
│   │                          category, classify each category into a tier,
│   │                          determine stronger/weaker category
│   ├── ai_insight.py         # Prompt construction + Gemini/Groq/mock provider chain
│   └── routes.py              # GET /api/questions, POST /api/submit
├── static/
│   ├── index.html               # Single page: sectioned quiz view + results view
│   ├── app.js                     # Fetches questions, tracks answers per section, renders results
│   └── style.css                    # Styling
├── app.py                                    # Dev entry point (python app.py)
├── requirements.txt
├── .env.example
└── README.md
```

---

## Part 1 — The Quiz

`app/questions.py` defines 8 questions split evenly across two categories,
**Communication** and **Problem-Solving**, each answered on a 1–5 scale
(Strongly Disagree → Strongly Agree). The frontend fetches these from
`GET /api/questions` — the question data lives in exactly one place, and the
frontend never hardcodes questions.

**A deliberate departure from the literal spec, worth flagging directly:**
the brief describes one page with all 8 questions and a Submit button
disabled until all 8 are answered. I instead built a **sectioned flow** —
one category's 4 questions per screen, with a "Section X of Y" label and a
Next button. The Next button for a section is disabled until that section's
4 questions are answered; the final section shows Submit instead of Next,
and Submit stays disabled until that section is complete too. The *effect*
is identical to what's asked (you cannot submit until all 8 questions have
been answered), but the mechanism is paginated rather than a single long
scroll. I made this choice because it's a more realistic layout for an
8-question, 2-category self-assessment and I think it reads better on
mobile widths, but it is a change from the literal description, not a
literal implementation of it, so I want that visible rather than glossed
over.

Answers accumulate across sections in `app.js`'s `state.answers` as the
person moves through the quiz, so by the time they reach Submit on the last
section, the full 8-answer set is ready to send. On submit, `POST
/api/submit` validates the answers, averages each category with
`scoring.calculate_scores`, and returns both the scores (e.g.,
"Communication: 3.75 / 5") and the AI insight in one response, displayed in
the results view.

**Another departure, also worth flagging directly:** the brief explicitly
says no backend is required and local state/local storage is sufficient. I
built a real Flask backend anyway. The reason is Part 2 — calling a real AI
provider from the browser directly would mean shipping the Gemini/Groq API
key in client-side JavaScript, visible to anyone who opens dev tools. Since
the brief also asks for "a real request shape" and "the integration logic,"
I judged that a working, key-safe integration was more useful to demonstrate
than a client-only version that could not safely call a real provider. The
backend is minimal on purpose: two routes, no database, no auth, session
state only to remember which 8 (randomly-sampled, from a pool of 16) questions
were shown to this browser, so `/api/submit` can validate answers against
exactly what was actually asked.

---

## Part 2 — AI-Generated Insight

`app/ai_insight.py` builds a prompt from the category averages *and* every
individual question/answer pair — not just the two averages — so the model
has something concrete to point to instead of inventing generic advice.
Each category's average is also classified into a tier (Strong / Average /
Needs Improvement, via `scoring.classify_tier`) so the model judges each
category on its own standing, not only on the gap between the two — a solid
4.2 shouldn't get flagged as "needing work" just because the other category
scored higher. The system prompt requires strict JSON output, forbids
phrases like "practice more," and forbids writing the literal tier label
words in the output (the tier only shapes tone/severity, never appears
verbatim in the sentence shown to the user).

### Example prompt (system message)

> You are a concise, honest career-development coach reviewing a person's
> self-assessment quiz. You will be given their average score (1-5) in two
> skill categories, a tier label for each category, and their individual
> answers within each category. Respond with STRICT JSON only... Rules: use
> the tier definitions only to decide tone, never write the literal tier
> label words; improvement_suggestion must name a specific technique,
> format, or exercise for the weaker category and must not say generic
> things like "practice more."

### Provider chain

The brief allows a mocked response if you don't have API access; I have access to both,
but built genuine fallback logic anyway rather than a single hardcoded provider,
since a provider outage shouldn't take the whole feature down:

1. **Gemini**, if `GEMINI_API_KEY` is set in `.env`.
2. **Groq**, if Gemini's key is missing, the call fails for any reason
   (network, auth, quota), or the response is truncated by the output token
   limit.
3. A **deterministic mocked response**, clearly labeled `[MOCKED]` both in
   the JSON payload and in the UI, if neither provider is configured or both
   fail. This means the app always returns a usable result, and the real
   integration path (prompt building, request shape, response parsing) is
   exercised even without live credentials — this is the "write the function
   that would make the real call, but have it call a mocked response
   instead" path the brief describes, kept in place as a genuine fallback
   rather than removed once real keys were added.

---

## What I skipped, and why

- **No database.** Not required by the brief; quiz state lives entirely in
  browser memory (plus a signed session cookie server-side, to remember
  which 8 questions were shown) for the duration of one attempt.
- **No automated test suite or CI pipeline.** Given more time I'd add unit
  tests for `scoring.py` and the provider fallback chain in `ai_insight.py`
  (mocking Gemini/Groq so tests stay deterministic and don't burn API
  quota), plus a GitHub Actions workflow to run them on every push. For now
  the app has been verified manually end-to-end, including against live
  Gemini and Groq keys.
- **No production WSGI entry point or deployment.** Not required by the
  brief. The app runs via `python app.py` for development only.
- **No second-pass quality check on the AI's output** (see Part 3, Q2) —
  right now a response can be structurally valid JSON but still vague, and
  nothing catches that automatically yet.
- **In-memory rate limiting** (Flask-Limiter's default storage) — fine for a
  single dev/demo process, but doesn't coordinate across multiple workers or
  instances. Flagged in code comments and in Part 3, Q1.
- **Not every edge case is handled** — e.g., a browser with cookies fully
  disabled would lose the session-based "which questions were shown"
  tracking on `/api/submit` and see a "please reload" message rather than a
  graceful automatic recovery.

---

## Part 3 — Written Explanation

### 1. What would break first at 1,000 concurrent users, and what's the smallest fix?

The first thing to fall over is almost certainly **the AI call blocking a
whole server worker for its full duration**. A typical sync WSGI worker
handles one request at a time; a Gemini or Groq call can easily take
1-3+ seconds. With a handful of workers, a burst of concurrent
`/api/submit` requests queues up fast and users start seeing timeouts, even
though the actual CPU work (scoring, JSON parsing) is trivial — the
bottleneck is workers sitting idle waiting on a network response.

The smallest fix is a **deployment/config change, not a code change**:
run behind a WSGI server using a worker class built for blocking I/O
(e.g. gunicorn with `gthread` or `gevent` workers) and raise the
worker/thread count. That lets each process hold many in-flight AI calls
instead of one, with no application code touched.

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