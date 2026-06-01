/* app.js — SiteHealth AI */

const API_URL = "/ask";

// ── DOM refs: connect screen ─────────────────────────────────
const connectScreen  = document.getElementById("connect-screen");
const appScreen      = document.getElementById("app-screen");
const connectForm    = document.getElementById("connect-form");
const tenantUrlInput = document.getElementById("tenant-url");
const apiTokenInput  = document.getElementById("api-token");
const connectBtn     = document.getElementById("connect-btn");
const connectError   = document.getElementById("connect-error");
const useDemoBtn     = document.getElementById("use-demo-btn");
const toggleTokenBtn = document.getElementById("toggle-token");
const disconnectBtn  = document.getElementById("disconnect-btn");
const navTenantLabel = document.getElementById("nav-tenant-label");

// ── DOM refs: app screen ─────────────────────────────────────
const questionInput  = document.getElementById("question-input");
const askBtn         = document.getElementById("ask-btn");
const chip1          = document.getElementById("chip-1");
const chip2          = document.getElementById("chip-2");
const chip3          = document.getElementById("chip-3");
const loadingSection = document.getElementById("loading-section");
const answerSection  = document.getElementById("answer-section");
const answerHeadline = document.getElementById("answer-headline");
const answerPara     = document.getElementById("answer-paragraph");
const answerChart    = document.getElementById("answer-chart");
const answerUncert   = document.getElementById("answer-uncertainty");
const errorBanner    = document.getElementById("error-banner");
const followupSection = document.getElementById("followup-section");
const followupChips   = document.getElementById("followup-chips");

let chartInstance = null;
let lastQuestion  = null;
let isFollowUp    = false;
let isLoading     = false;

// ════════════════════════════════════════════════════════════
// SESSION
// Credentials live only in sessionStorage — cleared on tab close.
// tenantUrl / token are null when using the demo (server uses env vars).
// ════════════════════════════════════════════════════════════

function getSession() {
  try {
    const raw = sessionStorage.getItem("sh_session");
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function saveSession(tenantUrl, token, label) {
  sessionStorage.setItem("sh_session", JSON.stringify({ tenantUrl, token, label }));
}

function clearSession() {
  sessionStorage.removeItem("sh_session");
}

// ════════════════════════════════════════════════════════════
// SCREEN TRANSITIONS
// ════════════════════════════════════════════════════════════

function showConnectScreen() {
  connectScreen.classList.remove("hidden");
  appScreen.classList.add("hidden");
}

function showAppScreen(session) {
  connectScreen.classList.add("hidden");
  appScreen.classList.remove("hidden");
  navTenantLabel.textContent = session.label || extractTenantName(session.tenantUrl) || "Connected";
}

function extractTenantName(url) {
  try { return new URL(url).hostname.split(".")[0]; }
  catch { return null; }
}

// ════════════════════════════════════════════════════════════
// CONNECT FORM
// ════════════════════════════════════════════════════════════

function setConnectBusy(busy) {
  connectBtn.disabled = busy;
  connectBtn.querySelector(".connect-btn__text").textContent =
    busy ? "Connecting…" : "Connect to Dynatrace";
}

function showConnectErr(msg) {
  connectError.textContent = msg;
  connectError.classList.remove("hidden");
}

function hideConnectErr() {
  connectError.classList.add("hidden");
}

function isValidDtUrl(url) {
  try {
    const p = new URL(url);
    return p.protocol === "https:" && p.hostname.endsWith(".apps.dynatrace.com");
  } catch { return false; }
}

connectForm.addEventListener("submit", (e) => {
  e.preventDefault();
  hideConnectErr();

  const tenantUrl = tenantUrlInput.value.trim();
  const token     = apiTokenInput.value.trim();

  if (!tenantUrl) { showConnectErr("Please enter your Dynatrace tenant URL."); return; }
  if (!isValidDtUrl(tenantUrl)) {
    showConnectErr("URL must be https://your-tenant.apps.dynatrace.com");
    return;
  }
  if (!token) { showConnectErr("Please enter your API token."); return; }
  if (!token.startsWith("dt0")) {
    showConnectErr("Token should start with dt0 — check you copied it correctly.");
    return;
  }

  const label = extractTenantName(tenantUrl);
  saveSession(tenantUrl, token, label);
  showAppScreen({ tenantUrl, token, label });
});

// Demo: pass null credentials → backend falls back to env vars
useDemoBtn.addEventListener("click", () => {
  saveSession(null, null, "Dynatrace Playground");
  showAppScreen({ tenantUrl: null, token: null, label: "Dynatrace Playground" });
});

disconnectBtn.addEventListener("click", () => {
  clearSession();
  setStateIdle();
  answerSection.classList.add("hidden");
  followupSection.classList.add("hidden");
  questionInput.value = "";
  lastQuestion = null;
  isFollowUp = false;
  showConnectScreen();
});

// Toggle token visibility
toggleTokenBtn.addEventListener("click", () => {
  const show = apiTokenInput.type === "password";
  apiTokenInput.type = show ? "text" : "password";
  toggleTokenBtn.setAttribute("aria-label", show ? "Hide token" : "Show token");
});

// ════════════════════════════════════════════════════════════
// APP STATE MACHINE
// ════════════════════════════════════════════════════════════

function setStateIdle() {
  isLoading = false;
  questionInput.disabled = false;
  askBtn.disabled = false;
  askBtn.querySelector(".btn-text").textContent = "Ask";
  loadingSection.classList.add("hidden");
  errorBanner.classList.add("hidden");
}

function setStateLoading() {
  isLoading = true;
  questionInput.disabled = true;
  askBtn.disabled = true;
  askBtn.querySelector(".btn-text").textContent = "…";
  answerSection.classList.add("hidden");
  followupSection.classList.add("hidden");
  loadingSection.classList.remove("hidden");
  errorBanner.classList.add("hidden");
}

function setStateAnswered(data) {
  isLoading = false;
  loadingSection.classList.add("hidden");
  questionInput.disabled = false;
  askBtn.disabled = false;
  askBtn.querySelector(".btn-text").textContent = "Ask";

  answerHeadline.textContent = data.headline;
  answerPara.textContent     = data.paragraph;

  if (data.chart_data && data.chart_data.labels && data.chart_data.labels.length > 0) {
    answerChart.classList.remove("hidden");
    renderChart(data.chart_data);
  } else {
    answerChart.classList.add("hidden");
    destroyChart();
  }

  answerUncert.classList.toggle("hidden", !data.uncertainty);
  answerSection.classList.remove("hidden");

  // Render follow-up chips
  followupChips.replaceChildren();
  const questions = Array.isArray(data.followup_questions) ? data.followup_questions : [];
  if (questions.length > 0) {
    questions.forEach((q) => {
      const btn = document.createElement("button");
      btn.className = "followup-chip";
      btn.textContent = q;
      btn.type = "button";
      btn.addEventListener("click", () => {
        lastQuestion = questionInput.value.trim() || lastQuestion;
        isFollowUp = true;
        questionInput.value = q;
        questionInput.focus();
        submitQuestion();
      });
      followupChips.appendChild(btn);
    });
    followupSection.classList.remove("hidden");
  } else {
    followupSection.classList.add("hidden");
  }
}

function setStateError(message) {
  isLoading = false;
  loadingSection.classList.add("hidden");
  questionInput.disabled = false;
  askBtn.disabled = false;
  askBtn.querySelector(".btn-text").textContent = "Ask";
  errorBanner.textContent = message;
  errorBanner.classList.remove("hidden");
}

// ════════════════════════════════════════════════════════════
// CHIPS & SUBMIT
// ════════════════════════════════════════════════════════════

function setupChips() {
  [chip1, chip2, chip3].forEach(chip => {
    chip.addEventListener("click", () => {
      questionInput.value = chip.dataset.question;
      questionInput.focus();
      submitQuestion();
    });
  });
}

async function submitQuestion() {
  if (isLoading) return;

  const question = questionInput.value.trim();

  if (!question) {
    setStateError("Please type a question before clicking Ask.");
    return;
  }
  if (question.length > 500) {
    setStateError("Your question is too long. Please keep it under 500 characters.");
    return;
  }

  // Capture follow-up context before setStateLoading clears state
  const followUpContext = isFollowUp ? lastQuestion : null;
  isFollowUp = false;
  lastQuestion = question;

  setStateLoading();

  const session = getSession();
  const headers = { "Content-Type": "application/json" };

  // Only attach custom credential headers when the user connected their own account
  if (session && session.tenantUrl) headers["X-DT-Tenant-URL"] = session.tenantUrl;
  if (session && session.token)     headers["X-DT-Token"]      = session.token;

  const body = { question };
  if (followUpContext) body.prev_question = followUpContext;

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });

    if (response.status === 429) {
      setStateError("You've asked several questions quickly. Please wait a moment and try again.");
      return;
    }
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      setStateError(err.detail || "Something went wrong. Please try again.");
      return;
    }

    const data = await response.json();
    setStateAnswered(data);

  } catch {
    setStateError("Couldn't reach the server. Check your connection and try again.");
  }
}

// ════════════════════════════════════════════════════════════
// CHART
// ════════════════════════════════════════════════════════════

function destroyChart() {
  if (chartInstance) { chartInstance.destroy(); chartInstance = null; }
}

function renderChart(chartData) {
  destroyChart();
  const ctx = answerChart.getContext("2d");
  const isBar = chartData.type === "bar";

  const gradient = ctx.createLinearGradient(0, 0, 0, 220);
  gradient.addColorStop(0, "rgba(14, 165, 233, 0.14)");
  gradient.addColorStop(1, "rgba(14, 165, 233, 0.01)");

  const barColors = chartData.labels.map((_, i) =>
    i === 0 ? "rgba(14, 165, 233, 0.75)" : "rgba(148, 163, 184, 0.35)"
  );
  const barBorders = chartData.labels.map((_, i) =>
    i === 0 ? "#0ea5e9" : "#94a3b8"
  );

  const dataset = isBar ? {
    label: chartData.unit || "Value",
    data: chartData.values,
    backgroundColor: barColors,
    borderColor: barBorders,
    borderWidth: 1.5,
    borderRadius: 6,
    borderSkipped: false,
  } : {
    label: chartData.unit || "Value",
    data: chartData.values,
    borderColor: "#0ea5e9",
    backgroundColor: gradient,
    borderWidth: 2,
    tension: 0.4,
    pointRadius: 3,
    pointBackgroundColor: "#0ea5e9",
    pointBorderColor: "#ffffff",
    pointBorderWidth: 2,
    fill: true,
  };

  chartInstance = new Chart(ctx, {
    type: isBar ? "bar" : "line",
    data: { labels: chartData.labels, datasets: [dataset] },
    options: {
      responsive: true,
      animation: { duration: 700, easing: "easeInOutQuart" },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#0f172a",
          borderColor: "rgba(14,165,233,0.25)",
          borderWidth: 1,
          titleColor: "#f1f5f9",
          bodyColor: "#94a3b8",
          cornerRadius: 8,
          padding: 12,
          callbacks: {
            label: (ctx) => `${ctx.parsed.y} ${chartData.unit || ""}`,
          },
        },
      },
      scales: {
        y: {
          beginAtZero: isBar,
          grid: { color: "rgba(148,163,184,0.12)" },
          ticks: { color: "#94a3b8", font: { family: "'Plus Jakarta Sans', sans-serif", size: 11 } },
          border: { color: "transparent" },
        },
        x: {
          grid: { display: false },
          ticks: {
            maxTicksLimit: isBar ? 10 : 8,
            color: "#94a3b8",
            font: { family: "'Plus Jakarta Sans', sans-serif", size: isBar ? 12 : 10 },
          },
          border: { color: "rgba(148,163,184,0.15)" },
        },
      },
    },
  });
}

// ════════════════════════════════════════════════════════════
// INIT
// ════════════════════════════════════════════════════════════

function init() {
  const session = getSession();

  if (session) {
    showAppScreen(session);
  } else {
    showConnectScreen();
  }

  setupChips();

  askBtn.addEventListener("click", submitQuestion);

  questionInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !askBtn.disabled) submitQuestion();
  });
}

document.addEventListener("DOMContentLoaded", init);
