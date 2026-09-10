/**
 * Evalix quiz front end. No build step, no framework — plain fetch + DOM.
 * Kept as one small file since the whole app is a single page; if this grew
 * past a couple of views it would be worth reaching for a framework instead.
 */

const SCALE_LABELS = ["Strongly Disagree", "Disagree", "Neutral", "Agree", "Strongly Agree"];

const state = {
  questions: [],
  categories: [],
  answers: {}, // { [questionId]: 1-5 }
};

const el = {
  quizView: document.getElementById("quiz-view"),
  resultsView: document.getElementById("results-view"),
  groups: document.getElementById("question-groups"),
  form: document.getElementById("quiz-form"),
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
  el.retakeBtn.addEventListener("click", resetToQuiz);

  try {
    const data = await fetchJSON("/api/questions");
    state.questions = data.questions;
    state.categories = data.categories;
    renderQuestions();
  } catch (err) {
    showError("Couldn't load the quiz. Please refresh the page.");
    console.error(err);
  }
}

function renderQuestions() {
  el.groups.innerHTML = "";

  for (const category of state.categories) {
    const section = document.createElement("div");
    section.className = "category";

    const title = document.createElement("h2");
    title.className = "category__title";
    title.textContent = category;
    section.appendChild(title);

    const questionsInCategory = state.questions.filter((q) => q.category === category);
    for (const question of questionsInCategory) {
      section.appendChild(renderQuestion(question));
    }

    el.groups.appendChild(section);
  }
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

  for (let value = 1; value <= 5; value++) {
    const optionLabel = document.createElement("label");
    optionLabel.className = "scale__option";

    const input = document.createElement("input");
    input.type = "radio";
    input.className = "scale__input";
    input.name = question.id;
    input.value = String(value);
    input.setAttribute("aria-label", `${SCALE_LABELS[value - 1]} (${value})`);
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

function updateProgress() {
  const answeredCount = Object.keys(state.answers).length;
  const total = state.questions.length;
  el.progressNote.textContent = `${answeredCount} of ${total} answered`;
  el.submitBtn.disabled = answeredCount < total;
}

async function handleSubmit(event) {
  event.preventDefault();
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

function resetToQuiz() {
  state.answers = {};
  el.form.reset();
  updateProgress();
  el.submitBtn.textContent = "See my results";
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