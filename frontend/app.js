/**
 * SANGYAN — Frontend Application Logic
 * Handles all 3 screens: input → analyzing → results
 */

// ============================================================
// STATE
// ============================================================

const API_BASE = "http://localhost:8000";

let state = {
  lang: "en",
  inputType: null,
  imageBase64: null,
  lastResult: null,
};

// ============================================================
// LANGUAGE TOGGLE
// ============================================================

function toggleLang() {
  state.lang = state.lang === "en" ? "hi" : "en";
  document.getElementById("lang-toggle").textContent = state.lang === "en" ? "हिंदी" : "English";
  updateLangText();
}

function updateLangText() {
  document.querySelectorAll("[data-en]").forEach((el) => {
    el.textContent = el.getAttribute(`data-${state.lang}`) || el.getAttribute("data-en");
  });
  document.querySelectorAll("[data-en]").forEach((el) => {
    const ph = el.getAttribute(`data-${state.lang}-placeholder`);
    if (ph) el.setAttribute("placeholder", ph);
  });

  const ta = document.getElementById("text-content");
  if (ta) {
    ta.setAttribute(
      "placeholder",
      state.lang === "hi"
        ? "संदिग्ध संदेश यहाँ चिपकाएं..."
        : "Paste the suspicious message here..."
    );
  }
}

// ============================================================
// INPUT TYPE SELECTION
// ============================================================

function selectInputType(type) {
  state.inputType = type;

  // Clear all selections
  document.querySelectorAll(".input-card").forEach((c) => c.classList.remove("selected"));
  document.getElementById("text-input-area").style.display = "none";
  document.getElementById("image-preview-area").style.display = "none";

  if (type === "screenshot") {
    document.getElementById("card-screenshot").classList.add("selected");
    document.getElementById("image-preview-area").style.display = "block";
    document.getElementById("file-input").click();
  } else if (type === "text") {
    document.getElementById("card-text").classList.add("selected");
    document.getElementById("text-input-area").style.display = "block";
    document.getElementById("text-content").setAttribute(
      "placeholder",
      state.lang === "hi"
        ? "संदिग्ध संदेश यहाँ चिपकाएं..."
        : "Paste the suspicious WhatsApp/Telegram message here..."
    );
    document.getElementById("text-content").focus();
  } else if (type === "url") {
    document.getElementById("card-url").classList.add("selected");
    document.getElementById("text-input-area").style.display = "block";
    document.getElementById("text-content").setAttribute(
      "placeholder",
      "https://... or @telegramhandle"
    );
    document.getElementById("text-content").focus();
  }
}

// ============================================================
// FILE UPLOAD
// ============================================================

function handleFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (e) => {
    state.imageBase64 = e.target.result; // full data URI
    const preview = document.getElementById("image-preview");
    preview.src = state.imageBase64;
    preview.style.display = "block";

    document.getElementById("upload-zone").style.display = "none";
    document.getElementById("analyze-img-btn").style.display = "flex";
  };
  reader.readAsDataURL(file);
}

// ============================================================
// ANALYZE
// ============================================================

async function analyzeContent() {
  let content = "";
  let inputType = state.inputType || "text";

  if (inputType === "screenshot") {
    if (!state.imageBase64) {
      showError("Please upload a screenshot first.");
      return;
    }
    content = state.imageBase64;
  } else {
    content = document.getElementById("text-content").value.trim();
    if (!content) {
      showError(state.lang === "hi" ? "कृपया पहले संदेश चिपकाएं।" : "Please paste a message first.");
      return;
    }
    // Auto-detect URL vs text vs handle
    if (inputType === "url" || isUrl(content)) {
      inputType = "url";
    } else if (isHandle(content)) {
      inputType = "handle";
    } else {
      inputType = "text";
    }
  }

  showScreen("screen-analyzing");
  animateSteps();

  try {
    const response = await fetch(`${API_BASE}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input_type: inputType, content }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "Server error" }));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }

    const data = await response.json();
    state.lastResult = data;

    // Brief pause so the animation completes
    await sleep(600);

    renderResults(data);
    showScreen("screen-results");
  } catch (err) {
    console.error("Analysis error:", err);
    showScreen("screen-input");
    showError(`Analysis failed: ${err.message}. Is the SANGYAN backend running?`);
  }
}

function isUrl(str) {
  return /^https?:\/\//i.test(str) || /^www\./i.test(str);
}

function isHandle(str) {
  return /^@[\w.]+$/.test(str.trim()) && str.length < 50;
}

// ============================================================
// ANALYZING ANIMATION
// ============================================================

function animateSteps() {
  const steps = [1, 2, 3, 4, 5, 6];
  steps.forEach((n, i) => {
    const el = document.getElementById(`step-${n}`);
    el.classList.remove("active", "done");
    el.querySelector(".step-icon").textContent = "⏳";
  });

  let current = 0;
  const interval = setInterval(() => {
    if (current > 0) {
      const prev = document.getElementById(`step-${current}`);
      prev.classList.remove("active");
      prev.classList.add("done");
      prev.querySelector(".step-icon").textContent = "✓";
    }
    current++;
    if (current > steps.length) {
      clearInterval(interval);
      return;
    }
    const el = document.getElementById(`step-${current}`);
    el.classList.add("active");
  }, 800);
}

// ============================================================
// RENDER RESULTS
// ============================================================

function renderResults(data) {
  const container = document.getElementById("results-container");
  const verdict = data.verdict.toLowerCase(); // stop | pause | trust

  const html = `
    ${renderVerdictBanner(data)}
    ${renderProofChain(data.proof_chain)}
    ${renderContradictions(data.contradictions)}
    ${renderNextSteps(data.next_steps, verdict)}
    ${renderRedFlags(data.red_flags)}
    ${renderEvidence(data.evidence)}
    ${renderMLSignal(data.ml_signal)}
    ${renderOfficialLinks(data.official_links)}
    <div class="caveat-box">⚠️ ${escapeHtml(data.caveat || "")}</div>
  `;

  container.innerHTML = html;

  // Animate ML bars
  setTimeout(() => {
    animateMLBars(data.ml_signal);
  }, 300);
}

// ---- Verdict banner ----

function renderVerdictBanner(data) {
  const v = data.verdict.toLowerCase();
  const emoji = v === "stop" ? "🔴" : v === "pause" ? "🟡" : "🟢";

  const verdictLabels = {
    stop: "STOP — CRITICAL CONTRADICTION FOUND",
    pause: "PAUSE — MORE VERIFICATION REQUIRED",
    trust: "TRUST ESTABLISHED",
  };

  const scoreColor = v === "stop" ? "var(--stop-color)" : v === "pause" ? "var(--pause-color)" : "var(--trust-color)";

  return `
    <div class="verdict-banner ${v}">
      <span class="verdict-emoji">${emoji}</span>
      <div class="verdict-label">${verdictLabels[v] || data.verdict}</div>
      <div class="verdict-score-row">
        <div class="score-ring" style="color:${scoreColor}">${data.trust_score}</div>
        <div class="score-label">Trust Score<br><small style="opacity:0.6">out of 100</small></div>
      </div>
    </div>
  `;
}

// ---- Proof chain ----

function renderProofChain(chain) {
  if (!chain || !chain.length) return "";

  const nodeEmojis = {
    claim: "📋", entity: "🏢", regulator: "⚖️", offer: "💰", payment: "💳"
  };

  const nodes = chain.map((node) => {
    const statusClass = node.status;
    const icon = statusClass === "verified" ? "✓" : statusClass === "contradicted" ? "✗" : "?";
    const emoji = nodeEmojis[node.node] || "●";

    return `
      <div class="chain-node ${statusClass}" title="${escapeHtml(node.detail || '')}">
        <div class="node-icon ${statusClass}">${emoji}</div>
        <div class="node-label">${node.node}</div>
        <div class="node-status ${statusClass}">${icon} ${capitalize(node.status)}</div>
      </div>
    `;
  }).join('<div style="width:24px;flex-shrink:0;"></div>');

  return `
    <div class="result-section">
      <div class="section-title">🔗 Proof Chain</div>
      <div class="proof-chain" style="margin-top:16px;">${nodes}</div>
    </div>
  `;
}

// ---- Contradictions ----

function renderContradictions(contradictions) {
  if (!contradictions || !contradictions.length) return "";

  const items = contradictions.map((c) =>
    `<div class="contradiction-item">⚡ ${escapeHtml(c)}</div>`
  ).join("");

  return `
    <div class="result-section">
      <div class="section-title">⚡ Contradictions Found</div>
      <div class="contradiction-list" style="margin-top:12px;">${items}</div>
    </div>
  `;
}

// ---- Next steps ----

function renderNextSteps(steps, verdict) {
  if (!steps || !steps.length) return "";

  const items = steps.map((step, i) => {
    const isDanger = step.toLowerCase().includes("do not") ||
                     step.toLowerCase().includes("never") ||
                     step.toLowerCase().includes("stop") ||
                     step.toLowerCase().includes("report immediately");
    const cls = isDanger ? "danger" : i === 0 ? "primary" : "";

    return `
      <div class="next-step-item ${cls}">
        <div class="step-num">${i + 1}</div>
        <div>${escapeHtml(step)}</div>
      </div>
    `;
  }).join("");

  return `
    <div class="result-section">
      <div class="section-title">👣 Next Safe Steps</div>
      <div class="next-steps-list" style="margin-top:12px;">${items}</div>
    </div>
  `;
}

// ---- Red flags ----

function renderRedFlags(flags) {
  if (!flags || !flags.length) {
    return `
      <div class="result-section">
        <div class="section-title">🚩 Red Flags</div>
        <p style="color:#64748b;font-size:0.85rem;margin-top:12px;">No red flag keywords detected.</p>
      </div>
    `;
  }

  const chips = flags.map((f) => `
    <div class="flag-chip" title="${escapeHtml(f.regulatory_note || '')}">
      ${escapeHtml(f.trigger)} <span class="flag-points">-${f.points}pts</span>
    </div>
  `).join("");

  return `
    <div class="result-section">
      <div class="section-title">🚩 Red Flags (${flags.length} detected)</div>
      <div class="red-flags-grid" style="margin-top:12px;">${chips}</div>
    </div>
  `;
}

// ---- Evidence table ----

function renderEvidence(evidence) {
  if (!evidence || !evidence.length) return "";

  const rows = evidence.map((e) => {
    const caveat = e.caveat ? `<div class="evidence-caveat">⚠️ ${escapeHtml(e.caveat)}</div>` : "";
    const detail = e.detail ? `<div style="font-size:0.78rem;color:#94a3b8;margin-top:4px;">${escapeHtml(e.detail)}</div>` : "";

    return `
      <tr>
        <td>${escapeHtml(e.check)}</td>
        <td><span class="badge ${e.result}">${e.result.replace(/_/g, " ")}</span></td>
        <td>
          <span class="evidence-source">${escapeHtml(e.source)}</span>
          ${detail}
          ${caveat}
        </td>
      </tr>
    `;
  }).join("");

  return `
    <div class="result-section">
      <div class="section-header" onclick="toggleSection(this)">
        <div class="section-title">🔍 Evidence Checked</div>
        <span class="section-toggle">▼</span>
      </div>
      <div class="section-body">
        <table class="evidence-table">
          <thead>
            <tr>
              <th>Check</th>
              <th>Result</th>
              <th>Source / Detail</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>
  `;
}

// ---- ML signal ----

function renderMLSignal(ml) {
  if (!ml) return "";

  const combinedPct = Math.round((ml.combined || 0) * 100);
  const lrPct = Math.round((ml.lr_score || 0) * 100);
  const murilPct = Math.round((ml.muril_score || 0) * 100);

  const barClass = combinedPct >= 80 ? "high" : combinedPct >= 50 ? "medium" : "low";

  const topWords = ml.top_words && ml.top_words.length
    ? `<div style="margin-top:12px;font-size:0.78rem;color:#94a3b8;">Triggering words:</div>
       <div class="top-words">${ml.top_words.map((w) => `<span class="word-chip">${escapeHtml(w)}</span>`).join("")}</div>`
    : "";

  const availability = (!ml.lr_available && !ml.muril_available)
    ? `<p style="color:#64748b;font-size:0.8rem;margin-top:8px;">⚠️ Models not yet trained. Run training scripts to enable AI analysis.</p>`
    : "";

  return `
    <div class="result-section">
      <div class="section-header" onclick="toggleSection(this)">
        <div class="section-title">🤖 AI Signal <small style="color:#64748b;font-weight:400;margin-left:6px;">(supporting only)</small></div>
        <span class="section-toggle">▼</span>
      </div>
      <div class="section-body">
        <div class="ml-signal-row">
          <div class="ml-bar-wrapper">
            <div class="ml-bar-label">
              <span>TF-IDF + LR</span>
              <span>${lrPct}%</span>
            </div>
            <div class="ml-bar">
              <div class="ml-bar-fill ${barClass}" id="ml-bar-lr" style="width:0%"></div>
            </div>
          </div>
          <div class="ml-bar-wrapper">
            <div class="ml-bar-label">
              <span>MuRIL</span>
              <span>${murilPct}%</span>
            </div>
            <div class="ml-bar">
              <div class="ml-bar-fill ${barClass}" id="ml-bar-muril" style="width:0%"></div>
            </div>
          </div>
          <div class="ml-bar-wrapper">
            <div class="ml-bar-label">
              <span><strong>Combined</strong></span>
              <span><strong>${combinedPct}%</strong></span>
            </div>
            <div class="ml-bar">
              <div class="ml-bar-fill ${barClass}" id="ml-bar-combined" style="width:0%"></div>
            </div>
          </div>
        </div>
        ${topWords}
        ${availability}
        <div class="ml-note">ℹ️ ${escapeHtml(ml.note || "")}</div>
      </div>
    </div>
  `;
}

function animateMLBars(ml) {
  if (!ml) return;
  const lrPct = Math.round((ml.lr_score || 0) * 100);
  const murilPct = Math.round((ml.muril_score || 0) * 100);
  const combinedPct = Math.round((ml.combined || 0) * 100);

  const setBar = (id, pct) => {
    const el = document.getElementById(id);
    if (el) el.style.width = pct + "%";
  };
  setTimeout(() => setBar("ml-bar-lr", lrPct), 100);
  setTimeout(() => setBar("ml-bar-muril", murilPct), 200);
  setTimeout(() => setBar("ml-bar-combined", combinedPct), 300);
}

// ---- Official links ----

function renderOfficialLinks(links) {
  if (!links || !links.length) return "";

  const linksHtml = links.map((l) => `
    <a href="${escapeHtml(l.url)}" target="_blank" rel="noopener" class="official-link">
      🔗 ${escapeHtml(l.label)}
    </a>
  `).join("");

  return `
    <div class="result-section">
      <div class="section-title">🔒 Verify Yourself</div>
      <div class="official-links-grid" style="margin-top:12px;">${linksHtml}</div>
    </div>
  `;
}

// ============================================================
// COLLAPSIBLE SECTIONS
// ============================================================

function toggleSection(header) {
  const body = header.nextElementSibling;
  const toggle = header.querySelector(".section-toggle");
  if (!body) return;

  if (body.style.display === "none") {
    body.style.display = "block";
    if (toggle) toggle.classList.add("open");
  } else {
    body.style.display = "none";
    if (toggle) toggle.classList.remove("open");
  }
}

// ============================================================
// NAVIGATION
// ============================================================

function showScreen(id) {
  document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
  const target = document.getElementById(id);
  if (target) {
    target.classList.add("active");
    window.scrollTo(0, 0);
  }
}

function goBack() {
  state.imageBase64 = null;
  state.lastResult = null;
  document.getElementById("text-content").value = "";
  document.getElementById("image-preview").style.display = "none";
  document.getElementById("upload-zone").style.display = "block";
  document.getElementById("analyze-img-btn").style.display = "none";
  document.querySelectorAll(".input-card").forEach((c) => c.classList.remove("selected"));
  document.getElementById("text-input-area").style.display = "none";
  document.getElementById("image-preview-area").style.display = "none";
  showScreen("screen-input");
}

// ============================================================
// SHARE
// ============================================================

function shareResult() {
  if (!state.lastResult) return;
  const data = state.lastResult;
  const verdict = data.verdict;
  const score = data.trust_score;
  const emoji = verdict === "STOP" ? "🔴" : verdict === "PAUSE" ? "🟡" : "🟢";

  const text = `SANGYAN Fraud Check Result
${emoji} Verdict: ${verdict}
Trust Score: ${score}/100
Red flags: ${data.red_flags.length}
Contradictions: ${data.contradictions.length}

Always verify at sebi.gov.in before sending money.
Report scams at cybercrime.gov.in`;

  if (navigator.share) {
    navigator.share({ title: "SANGYAN Fraud Check", text });
  } else {
    navigator.clipboard.writeText(text).then(() => {
      showError("Result copied to clipboard!", false);
    });
  }
}

// ============================================================
// UTILITIES
// ============================================================

function showError(msg, isError = true) {
  const existing = document.querySelector(".error-toast");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.className = "error-toast";
  toast.style.borderColor = isError ? "var(--stop-border)" : "var(--trust-border)";
  toast.style.color = isError ? "var(--stop-color)" : "var(--trust-color)";
  toast.style.background = isError ? "var(--stop-bg)" : "var(--trust-bg)";
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

function escapeHtml(str) {
  if (typeof str !== "string") return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function capitalize(str) {
  if (!str) return "";
  return str.charAt(0).toUpperCase() + str.slice(1).replace(/_/g, " ");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ============================================================
// DRAG AND DROP FOR SCREENSHOT
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
  const uploadZone = document.getElementById("upload-zone");
  if (!uploadZone) return;

  uploadZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadZone.style.borderColor = "rgba(167,139,250,0.7)";
  });

  uploadZone.addEventListener("dragleave", () => {
    uploadZone.style.borderColor = "";
  });

  uploadZone.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadZone.style.borderColor = "";
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith("image/")) {
      const dt = new DataTransfer();
      dt.items.add(file);
      document.getElementById("file-input").files = dt.files;
      handleFileUpload({ target: { files: dt.files } });
      state.inputType = "screenshot";
    }
  });

  // Keyboard shortcut: Ctrl+Enter to analyze
  document.getElementById("text-content").addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      analyzeContent();
    }
  });
});
