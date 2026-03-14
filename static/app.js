/**
 * Fraud Detection Dashboard client
 * - Action and status are separate (Start Demo button + Run status badge)
 * - Live summary strip (transactions | completed batches | suspicious found)
 * - Per-batch lane pills to visualize parallel progress
 * - Event log with category badges (Agent, Tool, Batch, Result, Error)
 * - Suspicious cards with stronger hierarchy + filters
 */

const BATCH_IDS = ["batch_1", "batch_2", "batch_3", "batch_4", "batch_5"];

const ui = {
  startButton: document.getElementById("start-demo-btn"),
  runStatus: document.getElementById("run-status"),
  activityLog: document.getElementById("activity-log"),
  suspiciousList: document.getElementById("suspicious-list"),
  suspiciousEmpty: document.getElementById("suspicious-empty"),

  summaryTransactions: document.getElementById("summary-transactions"),
  summaryBatches: document.getElementById("summary-batches"),
  summarySuspicious: document.getElementById("summary-suspicious"),

  filterBatch: document.getElementById("filter-batch"),
  filterRisk: document.getElementById("filter-risk"),
  filterMerchant: document.getElementById("filter-merchant"),
};

const state = {
  eventSource: null,
  isRunning: false,
  totalTransactions: 0,
  completedBatches: new Set(),
  batchSuspiciousCounts: Object.fromEntries(BATCH_IDS.map((id) => [id, 0])),
  suspiciousRecords: [],
  seenSuspiciousKeys: new Set(),
};

function nowTime() {
  return new Date().toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function suspiciousKey(record) {
  return `${record.batch_id || "unknown"}::${record.id || "unknown"}`;
}

function parseRisk(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function updateSummaryStrip() {
  if (ui.summaryTransactions) {
    ui.summaryTransactions.textContent = String(state.totalTransactions || 0);
  }
  if (ui.summaryBatches) {
    ui.summaryBatches.textContent = `${state.completedBatches.size}/5`;
  }
  if (ui.summarySuspicious) {
    ui.summarySuspicious.textContent = String(state.suspiciousRecords.length);
  }
}

function addLanePill(batchId, text) {
  const lane = document.getElementById(`batch-lane-${batchId}`);
  if (!lane) return;

  const pill = document.createElement("span");
  pill.className = "lane-pill";
  pill.textContent = `${nowTime()} ${text}`;
  lane.appendChild(pill);
}

function clearBatchLanes() {
  BATCH_IDS.forEach((batchId) => {
    const lane = document.getElementById(`batch-lane-${batchId}`);
    if (lane) lane.innerHTML = "";
  });
}

function initBatchCards() {
  state.completedBatches.clear();
  BATCH_IDS.forEach((batchId) => {
    state.batchSuspiciousCounts[batchId] = 0;
    updateBatchStatus(batchId, "pending", 0);
  });
  clearBatchLanes();
  updateSummaryStrip();
}

function updateBatchStatus(batchId, status, suspiciousCount) {
  const statusEl = document.getElementById(`batch-status-${batchId}`);
  const countEl = document.getElementById(`batch-suspicious-${batchId}`);
  if (!statusEl || !countEl) return;

  statusEl.textContent = status;
  statusEl.classList.remove("status-pending", "status-running", "status-completed");
  statusEl.classList.add(`status-${status}`);

  if (typeof suspiciousCount === "number" && Number.isFinite(suspiciousCount)) {
    state.batchSuspiciousCounts[batchId] = suspiciousCount;
  }
  countEl.textContent = String(state.batchSuspiciousCounts[batchId] || 0);

  if (status === "completed") {
    state.completedBatches.add(batchId);
  }
  updateSummaryStrip();
}

function incrementBatchSuspiciousCount(batchId) {
  const next = (state.batchSuspiciousCounts[batchId] || 0) + 1;
  const currentStatus = document.getElementById(`batch-status-${batchId}`)?.textContent || "running";
  updateBatchStatus(batchId, currentStatus, next);
}

function badgeMeta(eventType) {
  if (eventType === "agent_started" || eventType === "agent_completed") {
    return { label: "Agent", className: "badge-agent" };
  }
  if (eventType === "tool_called") {
    return { label: "Tool", className: "badge-tool" };
  }
  if (eventType === "batch_started" || eventType === "batch_completed") {
    return { label: "Batch", className: "badge-batch" };
  }
  if (eventType === "suspicious_added" || eventType === "run_completed") {
    return { label: "Result", className: "badge-result" };
  }
  if (eventType === "error") {
    return { label: "Error", className: "badge-error" };
  }
  return { label: "Info", className: "badge-batch" };
}

function addLogEntry(message, eventType = "info") {
  if (!ui.activityLog) return;

  const firstLine = ui.activityLog.querySelector(".log-entry");
  if (firstLine && firstLine.textContent?.includes("Waiting for events")) {
    ui.activityLog.innerHTML = "";
  }

  const meta = badgeMeta(eventType);
  const line = document.createElement("div");
  line.className = "log-entry";
  line.innerHTML = `
    <span class="log-badge ${meta.className}">${meta.label}</span>
    <span class="log-text">[${nowTime()}] ${escapeHtml(message)}</span>
  `;

  ui.activityLog.appendChild(line);
  ui.activityLog.scrollTop = ui.activityLog.scrollHeight;
}

function renderSuspiciousList() {
  if (!ui.suspiciousList) return;

  const batchFilter = ui.filterBatch?.value || "all";
  const minRisk = parseRisk(ui.filterRisk?.value || 0);
  const merchantFilter = (ui.filterMerchant?.value || "").trim().toLowerCase();

  const filtered = state.suspiciousRecords.filter((record) => {
    if (batchFilter !== "all" && record.batch_id !== batchFilter) return false;
    if (parseRisk(record.risk_score) < minRisk) return false;
    if (merchantFilter && !String(record.merchant || "").toLowerCase().includes(merchantFilter)) return false;
    return true;
  });

  ui.suspiciousList.innerHTML = "";

  if (filtered.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.id = "suspicious-empty";
    empty.textContent = "No suspicious transactions for current filter.";
    ui.suspiciousList.appendChild(empty);
    ui.suspiciousEmpty = empty;
    return;
  }

  filtered.forEach((record) => {
    const reasons = Array.isArray(record.reasons) ? record.reasons : [];
    const reasonHtml = reasons.length
      ? reasons.map((reason) => `<span class="reason-chip">${escapeHtml(reason)}</span>`).join("")
      : "<span class=\"reason-chip\">n/a</span>";

    const riskScore = parseRisk(record.risk_score);
    const amountText = Number.isFinite(Number(record.amount)) ? `$${Number(record.amount).toFixed(2)}` : "n/a";

    const card = document.createElement("article");
    card.className = "txn-card";
    card.innerHTML = `
      <div class="txn-header">
        <h3>${escapeHtml(record.id || "unknown")}</h3>
        <span class="risk-pill">Risk ${escapeHtml(riskScore.toFixed(2))}</span>
      </div>
      <div class="txn-subline">
        ${escapeHtml(record.merchant || "n/a")} • ${escapeHtml(record.location || "n/a")} • ${escapeHtml(record.channel || "n/a")}
      </div>
      <div class="txn-fields">
        <div><strong>Amount:</strong> ${escapeHtml(amountText)}</div>
        <div><strong>Batch:</strong> ${escapeHtml(record.batch_id || "n/a")}</div>
      </div>
      <div style="margin-top:0.4rem;"><strong>Reasons:</strong></div>
      <div class="reason-chips">${reasonHtml}</div>
      <details class="debug">
        <summary>Debug details</summary>
        <div><strong>Seeded test case:</strong> ${record.isSeedFraud ? "Yes" : "No"}</div>
      </details>
    `;

    ui.suspiciousList.appendChild(card);
  });
}

function pushSuspiciousRecord(record) {
  const key = suspiciousKey(record);
  if (state.seenSuspiciousKeys.has(key)) return;

  state.seenSuspiciousKeys.add(key);
  state.suspiciousRecords.unshift(record);
  updateSummaryStrip();
  renderSuspiciousList();
}

function clearSuspiciousPanel() {
  state.suspiciousRecords = [];
  state.seenSuspiciousKeys.clear();
  renderSuspiciousList();
}

async function restoreSuspiciousRecords() {
  try {
    const response = await fetch("/suspicious");
    if (!response.ok) return;

    const payload = await response.json();
    const records = Array.isArray(payload.suspicious_transactions) ? payload.suspicious_transactions : [];

    records.forEach((record) => {
      pushSuspiciousRecord(record);
      if (record.batch_id && BATCH_IDS.includes(record.batch_id)) {
        incrementBatchSuspiciousCount(record.batch_id);
      }
    });

    if (records.length > 0) {
      addLogEntry(`Restored ${records.length} suspicious transaction(s) from state.`, "result");
    }
  } catch (error) {
    addLogEntry(`Could not restore previous suspicious transactions: ${error}`, "error");
  }
}

function setRunStatus(text) {
  if (!ui.runStatus) return;
  ui.runStatus.textContent = text;
}

function handleEvent(event) {
  const type = event.type || "unknown";
  const batchId = event.batch_id;

  switch (type) {
    case "batch_started": {
      if (batchId) {
        updateBatchStatus(batchId, "running");
        addLanePill(batchId, "started");
      }
      addLogEntry(event.message || `${batchId} started`, type);
      break;
    }
    case "batch_completed": {
      if (batchId) {
        const count = Number(event.suspicious_count);
        const safeCount = Number.isFinite(count) ? count : state.batchSuspiciousCounts[batchId] || 0;
        updateBatchStatus(batchId, "completed", safeCount);
        addLanePill(batchId, "completed");
      }
      addLogEntry(event.message || `${batchId} completed`, type);
      break;
    }
    case "agent_started": {
      if (batchId) addLanePill(batchId, "agent ▶");
      addLogEntry(event.message || `${batchId} agent started`, type);
      break;
    }
    case "agent_completed": {
      if (batchId) addLanePill(batchId, "agent ✓");
      addLogEntry(event.message || `${batchId} agent completed`, type);
      break;
    }
    case "tool_called": {
      if (batchId) addLanePill(batchId, "tool");
      addLogEntry(event.message || `${batchId} tool called`, type);
      break;
    }
    case "suspicious_added": {
      const transaction = event.transaction || {};
      pushSuspiciousRecord(transaction);
      if (batchId && BATCH_IDS.includes(batchId)) {
        incrementBatchSuspiciousCount(batchId);
        addLanePill(batchId, "suspicious");
      }
      addLogEntry(event.message || `Suspicious transaction added in ${batchId}`, type);
      break;
    }
    case "error": {
      addLogEntry(`ERROR: ${event.message || "unknown error"}`, type);
      if (batchId && BATCH_IDS.includes(batchId)) {
        addLanePill(batchId, "error");
      }
      setRunStatus("Run Error");
      break;
    }
    case "run_completed": {
      state.isRunning = false;
      if (ui.startButton) ui.startButton.disabled = false;
      setRunStatus("Run Completed");

      if (Number.isFinite(Number(event.total_transactions))) {
        state.totalTransactions = Number(event.total_transactions);
      }
      updateSummaryStrip();
      addLogEntry(event.message || "Run completed", type);
      break;
    }
    default: {
      addLogEntry(`Unhandled event: ${type}`, "batch");
      break;
    }
  }
}

function connectEventStream() {
  if (state.eventSource) {
    state.eventSource.close();
  }

  const source = new EventSource("/events");
  state.eventSource = source;

  source.onopen = () => {
    addLogEntry("Connected to live event stream.", "batch");
  };

  source.onmessage = (rawEvent) => {
    try {
      const parsed = JSON.parse(rawEvent.data);
      handleEvent(parsed);
    } catch (error) {
      addLogEntry(`Failed to parse SSE event: ${error}`, "error");
    }
  };

  source.onerror = () => {
    addLogEntry("Event stream connection issue. Browser will retry automatically.", "error");
  };
}

async function startDemo() {
  if (state.isRunning) {
    addLogEntry("A demo run is already in progress.", "batch");
    return;
  }

  state.isRunning = true;
  if (ui.startButton) ui.startButton.disabled = true;
  setRunStatus("Run Starting");

  // Reset visual state for a fresh run
  state.totalTransactions = 100;
  initBatchCards();
  clearSuspiciousPanel();
  updateSummaryStrip();

  addLogEntry("Starting demo run...", "batch");

  try {
    const response = await fetch("/start-demo", { method: "POST" });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(payload.message || `Request failed (${response.status})`);
    }

    setRunStatus("Run Running");
    addLogEntry(payload.message || "Demo started.", "batch");
  } catch (error) {
    state.isRunning = false;
    if (ui.startButton) ui.startButton.disabled = false;
    setRunStatus("Run Error");
    addLogEntry(`Failed to start demo: ${error}`, "error");
  }
}

function attachEventHandlers() {
  if (ui.startButton) {
    ui.startButton.addEventListener("click", startDemo);
  }

  ui.filterBatch?.addEventListener("change", renderSuspiciousList);
  ui.filterRisk?.addEventListener("input", renderSuspiciousList);
  ui.filterMerchant?.addEventListener("input", renderSuspiciousList);
}

function bootstrap() {
  initBatchCards();
  setRunStatus("Run Idle");
  updateSummaryStrip();
  attachEventHandlers();
  connectEventStream();
  restoreSuspiciousRecords();
}

document.addEventListener("DOMContentLoaded", bootstrap);
