const API = ""; // same-origin

/* ---------- view switching ---------- */
const links = document.querySelectorAll(".link-btn");
const views = document.querySelectorAll(".view");

function showView(name) {
  views.forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
  links.forEach((l) => l.classList.toggle("active", l.dataset.view === name));
  if (name === "knowledge") loadKnowledgeStats();
  if (name === "history") loadHistory();
}
links.forEach((l) => l.addEventListener("click", () => showView(l.dataset.view)));
showView("research");

/* ---------- research: streaming ---------- */
const form = document.getElementById("research-form");
const input = document.getElementById("query-input");
const runBtn = document.getElementById("run-btn");
const traceList = document.getElementById("trace-list");
const traceStatus = document.getElementById("trace-status");
const reportBody = document.getElementById("report-body");

let stepCount = 0;

function resetTrace() {
  stepCount = 0;
  traceList.innerHTML = "";
  reportBody.innerHTML = '<p class="report-empty">Working on it…</p>';
}

function addStep(kind, title, body) {
  stepCount += 1;
  const li = document.createElement("li");
  li.className = `trace-step kind-${kind}`;
  li.innerHTML = `
    <span class="step-num">${String(stepCount).padStart(2, "0")}</span>
    <span class="step-kind">${title}</span>
    ${body ? `<pre>${escapeHtml(body)}</pre>` : ""}
  `;
  traceList.appendChild(li);
  traceList.scrollTop = traceList.scrollHeight;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function renderMarkdownish(text) {
  // Minimal, dependency-free markdown-ish rendering — good enough for
  // agent-written reports (headings, bold, bullets, links).
  let html = escapeHtml(text)
    .replace(/^### (.*)$/gm, "<h3>$1</h3>")
    .replace(/^## (.*)$/gm, "<h2>$1</h2>")
    .replace(/^# (.*)$/gm, "<h1>$1</h1>")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/^- (.*)$/gm, "<li>$1</li>")
    .replace(/\n{2,}/g, "</p><p>");
  return `<p>${html}</p>`;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const query = input.value.trim();
  if (!query) return;

  resetTrace();
  runBtn.disabled = true;
  traceStatus.textContent = "running";
  traceStatus.className = "status running";

  try {
    const res = await fetch(`${API}/api/research`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const parts = buffer.split("\n\n");
      buffer = parts.pop(); // keep the last, possibly-incomplete chunk

      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        const event = JSON.parse(line.slice(5).trim());
        handleEvent(event);
      }
    }

    traceStatus.textContent = "done";
    traceStatus.className = "status done";
  } catch (err) {
    addStep("error", "error", String(err));
    traceStatus.textContent = "error";
    traceStatus.className = "status error";
  } finally {
    runBtn.disabled = false;
  }
});

function handleEvent(event) {
  switch (event.type) {
    case "session":
      break;
    case "reasoning":
      addStep("reasoning", "reasoning", event.text);
      break;
    case "tool_call":
      addStep("tool_call", `tool call · ${event.tool}`, JSON.stringify(event.input, null, 2));
      break;
    case "tool_result":
      addStep(
        "tool_result",
        `tool result · ${event.tool}`,
        JSON.stringify(event.output, null, 2).slice(0, 1200)
      );
      break;
    case "final":
      addStep("final", "final answer", null);
      reportBody.innerHTML = renderMarkdownish(event.text);
      break;
    case "error":
      addStep("error", "error", event.message);
      reportBody.innerHTML = `<p class="report-empty">The agent hit an error — see the trace.</p>`;
      break;
  }
}

/* ---------- knowledge base ---------- */
const uploadForm = document.getElementById("upload-form");
const fileInput = document.getElementById("file-input");
const uploadStatus = document.getElementById("upload-status");
const kbStats = document.getElementById("kb-stats");

uploadForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const file = fileInput.files[0];
  if (!file) return;

  uploadStatus.textContent = "indexing…";
  const fd = new FormData();
  fd.append("file", file);

  try {
    const res = await fetch(`${API}/api/documents`, { method: "POST", body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || "upload failed");
    const data = await res.json();
    uploadStatus.textContent = `indexed "${data.filename}" — ${data.chunks_indexed} chunks`;
    fileInput.value = "";
    loadKnowledgeStats();
  } catch (err) {
    uploadStatus.textContent = `error: ${err.message}`;
  }
});

async function loadKnowledgeStats() {
  kbStats.textContent = "loading…";
  const res = await fetch(`${API}/api/knowledge-base`);
  const data = await res.json();
  if (!data.documents.length) {
    kbStats.textContent = "No documents indexed yet.";
    return;
  }
  kbStats.innerHTML =
    `${data.chunks} chunks across ${data.documents.length} document(s):<br>` +
    data.documents.map((d) => `&nbsp;&nbsp;· <span class="doc-name">${escapeHtml(d)}</span>`).join("<br>");
}

/* ---------- history ---------- */
const historyList = document.getElementById("history-list");

async function loadHistory() {
  historyList.innerHTML = '<li class="hint">loading…</li>';
  const res = await fetch(`${API}/api/history`);
  const sessions = await res.json();
  if (!sessions.length) {
    historyList.innerHTML = '<li class="hint">No sessions yet — run a query first.</li>';
    return;
  }
  historyList.innerHTML = "";
  sessions.forEach((s) => {
    const li = document.createElement("li");
    li.className = "history-item";
    li.innerHTML = `
      <div class="history-query">${escapeHtml(s.query)}</div>
      <div class="history-meta">${new Date(s.created_at).toLocaleString()} · ${
      s.final_report ? "completed" : "incomplete"
    }</div>
    `;
    li.addEventListener("click", () => loadHistoryDetail(s.id));
    historyList.appendChild(li);
  });
}

async function loadHistoryDetail(id) {
  const res = await fetch(`${API}/api/history/${id}`);
  const session = await res.json();
  showView("research");
  input.value = session.query;
  resetTrace();
  session.trace.forEach(handleEvent);
  traceStatus.textContent = session.final_report ? "done" : "incomplete";
  traceStatus.className = `status ${session.final_report ? "done" : "idle"}`;
}
