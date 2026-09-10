import random

CATEGORIES = ["Communication", "Problem-Solving"]

QUESTIONS_PER_CATEGORY = 4

QUESTION_POOL = [
    {"id": "comm_1", "category": "Communication",
     "text": "I explain complex ideas in a way that others can easily follow."},
    {"id": "comm_2", "category": "Communication",
     "text": "I actively listen and ask clarifying questions before responding."},
    {"id": "comm_3", "category": "Communication",
     "text": "I adjust my tone and level of detail depending on who I'm talking to."},
    {"id": "comm_4", "category": "Communication",
     "text": "I give feedback in a way that is clear, direct, and constructive."},
    {"id": "comm_5", "category": "Communication",
     "text": "I can summarize a long discussion into its key points in a sentence or two."},
    {"id": "comm_6", "category": "Communication",
     "text": "I notice when someone is confused and adjust my explanation before they have to ask."},
    {"id": "comm_7", "category": "Communication",
     "text": "I write messages that get straight to the point without losing important context."},
    {"id": "comm_8", "category": "Communication",
     "text": "I'm comfortable disagreeing with someone respectfully rather than staying quiet."},
    {"id": "prob_1", "category": "Problem-Solving",
     "text": "I break large, ambiguous problems into smaller, concrete steps."},
    {"id": "prob_2", "category": "Problem-Solving",
     "text": "I consider more than one possible solution before committing to one."},
    {"id": "prob_3", "category": "Problem-Solving",
     "text": "I use evidence or data to guide decisions rather than relying on gut feel alone."},
    {"id": "prob_4", "category": "Problem-Solving",
     "text": "I stay focused and methodical when I hit an unexpected obstacle."},
    {"id": "prob_5", "category": "Problem-Solving",
     "text": "I can tell the difference between the root cause of a problem and its symptoms."},
    {"id": "prob_6", "category": "Problem-Solving",
     "text": "I test my assumptions early instead of building on them untested."},
    {"id": "prob_7", "category": "Problem-Solving",
     "text": "I know when to ask for help rather than spending hours stuck alone."},
    {"id": "prob_8", "category": "Problem-Solving",
     "text": "I can explain why a solution failed, not just that it failed."},
]

QUESTIONS_BY_ID = {q["id"]: q for q in QUESTION_POOL}

QUESTIONS = QUESTION_POOL


def pick_random_questions(n_per_category=QUESTIONS_PER_CATEGORY, rng=random):
    """
    Return a fresh list of n_per_category randomly sampled questions from
    each category (which 4 are picked is random, and their order is shuffled
    too since random.sample() doesn't preserve pool order).

    `rng` defaults to the `random` module but accepts a seeded
    random.Random() instance for deterministic tests.
    """
    selected = []
    for category in CATEGORIES:
        pool = [q for q in QUESTION_POOL if q["category"] == category]
        selected.extend(rng.sample(pool, n_per_category))
    return selected