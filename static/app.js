/**
 * Evalix quiz front end. No build step, no framework — plain fetch + DOM.
 * Kept as one small file since the whole app is a single page; if this grew
 * past a couple of views it would be worth reaching for a framework instead.
 *
 * Section flow
 * ------------
 * Questions are grouped by category (state.categories, in server order) and
 * shown one category at a time as a "section". The person answers every
 * question in the current section, clicks Next to advance, and only sees
 * the Submit button on the final section. state.answers accumulates across
 * every section (it's never cleared when moving between sections), so the
 * final submit still sends the complete answer set for all categories.
 */

const SCALE_LABELS = ["Strongly Disagree", "Disagree", "Neutral", "Agree", "Strongly Agree"];

const state = {
  questions: [],
  categories: [],
  answers: {}, // { [questionId]: 1-5 } -- accumulates across all sections
  sectionIndex: 0, // which category (index into state.categories) is showing
};

const el = {
  quizView: document.getElementById("quiz-view"),
  resultsView: document.getElementById("results-view"),
  sectionProgress: document.getElementById("section-progress"),
  groups: document.getElementById("question-groups"),
  form: document.getElementById("quiz-form"),
  backBtn: document.getElementById("back-btn"),
  nextBtn: document.getElementById("next-btn"),
  submitBtn: document.getElementById("submit-btn"),
  progressNote: document.getElementById("progress-note"),
  scoreSummary: document.getElementById("score-summary"),
  insightStronger: document.getElementById("insight-stronger"),
  insightSuggestion: document.getElementById("insight-suggestion"),
  insightModeNote: document.getElementById("insight-mode-note"),
  retakeBtn: document.getElementById("retake-btn"),
  errorBanner: document.getElementById("error-banner"),
};

init();

async function init() {
  el.form.addEventListener("submit", handleSubmit);
  el.nextBtn.addEventListener("click", handleNext);
  el.backBtn.addEventListener("click", handleBack);
  el.retakeBtn.addEventListener("click", startNewQuiz);

  await loadQuestions();
}

/**
 * Fetches a fresh, randomly-sampled set of questions from the server (the
 * server also records which ids it sent in this browser's session cookie,
 * so /api/submit can validate against exactly what was shown). Called on
 * first load AND every time "Retake the quiz" is clicked, so each attempt
 * can genuinely show a different 4-of-8 selection per category.
 */
async function loadQuestions() {
  try {
    const data = await fetchJSON("/api/questions");
    state.questions = data.questions;
    state.categories = data.categories;
    state.answers = {};
    state.sectionIndex = 0;
    renderCurrentSection();
  } catch (err) {
    showError("Couldn't load the quiz. Please refresh the page.");
    console.error(err);
  }
}

function currentCategory() {
  return state.categories[state.sectionIndex];
}

function isLastSection() {
  return state.sectionIndex === state.categories.length - 1;
}

function questionsForCategory(category) {
  return state.questions.filter((q) => q.category === category);
}

/**
 * Renders only the CURRENT section's category and its questions, updates
 * the "Section X of Y" label, and refreshes progress/button state to match.
 */
function renderCurrentSection() {
  const category = currentCategory();
  const questionsInSection = questionsForCategory(category);

  el.sectionProgress.textContent = `Section ${state.sectionIndex + 1} of ${state.categories.length}`;

  el.groups.innerHTML = "";
  const section = document.createElement("div");
  section.className = "category";

  const title = document.createElement("h2");
  title.className = "category__title";
  title.textContent = category;
  section.appendChild(title);

  for (const question of questionsInSection) {
    section.appendChild(renderQuestion(question));
  }

  el.groups.appendChild(section);

  updateProgress();
  updateButtonVisibility();
}

function renderQuestion(question) {
  const wrapper = document.createElement("div");
  wrapper.className = "question";

  const text = document.createElement("p");
  text.className = "question__text";
  text.textContent = question.text;
  wrapper.appendChild(text);

  const scale = document.createElement("div");
  scale.className = "scale";
  scale.setAttribute("role", "radiogroup");
  scale.setAttribute("aria-label", question.text);

  const existingAnswer = state.answers[question.id];

  for (let value = 1; value <= 5; value++) {
    const optionLabel = document.createElement("label");
    optionLabel.className = "scale__option";

    const input = document.createElement("input");
    input.type = "radio";
    input.className = "scale__input";
    input.name = question.id;
    input.value = String(value);
    input.setAttribute("aria-label", `${SCALE_LABELS[value - 1]} (${value})`);
    // Re-check a previously chosen answer when navigating back to a
    // section, since the DOM for it is rebuilt fresh each time.
    if (existingAnswer === value) {
      input.checked = true;
    }
    input.addEventListener("change", () => handleAnswerChange(question.id, value));

    const box = document.createElement("span");
    box.className = "scale__box";
    box.textContent = String(value);
    box.setAttribute("aria-hidden", "true");

    optionLabel.appendChild(input);
    optionLabel.appendChild(box);
    scale.appendChild(optionLabel);
  }

  wrapper.appendChild(scale);

  const labels = document.createElement("div");
  labels.className = "scale__labels";
  labels.innerHTML = `<span>${SCALE_LABELS[0]}</span><span>${SCALE_LABELS[4]}</span>`;
  wrapper.appendChild(labels);

  return wrapper;
}

function handleAnswerChange(questionId, value) {
  state.answers[questionId] = value;
  updateProgress();
}

/**
 * Progress and the Next/Submit enabled state are both scoped to the
 * CURRENT section only -- you don't need every category answered to
 * advance past section 1, just that section's own questions.
 */
function updateProgress() {
  const questionsInSection = questionsForCategory(currentCategory());
  const answeredInSection = questionsInSection.filter((q) => state.answers[q.id] !== undefined).length;
  const total = questionsInSection.length;

  el.progressNote.textContent = `${answeredInSection} of ${total} answered`;

  const sectionComplete = answeredInSection === total;
  el.nextBtn.disabled = !sectionComplete;
  el.submitBtn.disabled = !sectionComplete;
}

function updateButtonVisibility() {
  el.backBtn.classList.toggle("hidden", state.sectionIndex === 0);

  if (isLastSection()) {
    el.nextBtn.classList.add("hidden");
    el.submitBtn.classList.remove("hidden");
  } else {
    el.nextBtn.classList.remove("hidden");
    el.submitBtn.classList.add("hidden");
  }
}

function handleNext() {
  if (el.nextBtn.disabled) return; // guard against Enter-key submits etc.
  state.sectionIndex += 1;
  renderCurrentSection();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function handleBack() {
  state.sectionIndex -= 1;
  renderCurrentSection();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function handleSubmit(event) {
  event.preventDefault();
  if (!isLastSection() || el.submitBtn.disabled) return; // guard, mirrors button state
  hideError();

  el.submitBtn.disabled = true;
  el.submitBtn.textContent = "Scoring…";

  try {
    const data = await fetchJSON("/api/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers: state.answers }),
    });
    renderResults(data);
    showResultsView();
  } catch (err) {
    showError(err.message || "Something went wrong scoring your answers. Please try again.");
    console.error(err);
    el.submitBtn.disabled = false;
    el.submitBtn.textContent = "See my results";
  }
}

function renderResults(data) {
  el.scoreSummary.innerHTML = "";
  for (const category of state.categories) {
    const row = document.createElement("div");
    row.className = "score-row";

    const label = document.createElement("span");
    label.className = "score-row__label";
    label.textContent = category;

    const value = document.createElement("span");
    value.className = "score-row__value";
    value.textContent = `${data.scores[category].toFixed(2)} / 5`;

    row.appendChild(label);
    row.appendChild(value);
    el.scoreSummary.appendChild(row);
  }

  el.insightStronger.textContent = data.insight.stronger_category_sentence;
  el.insightSuggestion.textContent = data.insight.improvement_suggestion;

  const isMocked = data.insight.stronger_category_sentence.includes("[MOCKED]");
  if (isMocked) {
    el.insightModeNote.textContent =
      "This insight is a mocked response (no AI API key configured on the server).";
    el.insightModeNote.classList.remove("hidden");
  } else {
    el.insightModeNote.classList.add("hidden");
  }
}

function showResultsView() {
  el.quizView.classList.add("hidden");
  el.resultsView.classList.remove("hidden");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

/**
 * Starts an entirely new attempt: fetches a fresh random 4-per-category
 * selection from the server (not just resetting local answers to the same
 * old questions), resets the form and section index, and switches back to
 * the quiz view.
 */
async function startNewQuiz() {
  hideError();
  el.submitBtn.textContent = "See my results";
  el.form.reset();

  await loadQuestions();

  el.resultsView.classList.add("hidden");
  el.quizView.classList.remove("hidden");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function showError(message) {
  el.errorBanner.textContent = message;
  el.errorBanner.classList.remove("hidden");
}

function hideError() {
  el.errorBanner.classList.add("hidden");
}

async function fetchJSON(url, options) {
  const response = await fetch(url, options);
  let body = null;
  try {
    body = await response.json();
  } catch {
    // no JSON body
  }
  if (!response.ok) {
    throw new Error((body && body.error) || `Request failed (${response.status})`);
  }
  return body;
}