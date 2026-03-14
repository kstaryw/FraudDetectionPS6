/**
 * Fraud Detection PS-6 Dashboard client
 *
 * Responsibilities:
 * - Initialize batch cards (batch_1 to batch_5)
 * - Start demo run via POST /start-demo
 * - Listen to SSE events from /events
 * - Update Batch Status, Activity Log, and Suspicious Transactions in near real time
 */

// -----------------------------------------------------------------------------
// Constants and UI references
// -----------------------------------------------------------------------------

const BATCH_IDS = ["batch_1", "batch_2", "batch_3", "batch_4", "batch_5"];

const ui = {
  startButton: document.getElementById("start-demo-btn") || document.getElementById("startBtn"),
  runStatus: document.getElementById("run-status"),
  activityLog: document.getElementById("activity-log") || document.getElementById("activityLog"),
  suspiciousList: document.getElementById("suspicious-list") || document.getElementById("transactionsList"),
  suspiciousEmpty: document.getElementById("suspicious-empty"),
};

const state = {
  eventSource: null,
  isRunning: false,
  batchSuspiciousCounts: Object.fromEntries(BATCH_IDS.map((id) => [id, 0])),
  seenSuspiciousKeys: new Set(),
};

// -----------------------------------------------------------------------------
// Utility helpers
// -----------------------------------------------------------------------------

/**
 * Format a local timestamp string used in activity log lines.
 * @returns {string}
 */
function nowTime() {
  return new Date().toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/**
 * Escape text before inserting into innerHTML.
 * @param {unknown} value
 * @returns {string}
 */
function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

/**
 * Create a stable key used to avoid duplicate suspicious cards.
 * @param {{id?: string, batch_id?: string}} record
 * @returns {string}
 */
function suspiciousKey(record) {
  return `${record.batch_id || "unknown"}::${record.id || "unknown"}`;
}

// -----------------------------------------------------------------------------
// Batch status panel
// -----------------------------------------------------------------------------

/**
 * Initialize/Reset all batch cards to pending state.
 */
function initBatchCards() {
  BATCH_IDS.forEach((batchId) => {
    state.batchSuspiciousCounts[batchId] = 0;
    updateBatchStatus(batchId, "pending", 0);
  });
}

/**
 * Update one batch card's status and suspicious count.
 * @param {string} batchId
 * @param {"pending"|"running"|"completed"} status
 * @param {number=} suspiciousCount
 */
function updateBatchStatus(batchId, status, suspiciousCount) {
  const statusEl = document.getElementById(`batch-status-${batchId}`);
  const countEl = document.getElementById(`batch-suspicious-${batchId}`);

  if (!statusEl || !countEl) {
    return;
  }

  statusEl.textContent = status;
  statusEl.classList.remove("status-pending", "status-running", "status-completed");
  statusEl.classList.add(`status-${status}`);

  if (typeof suspiciousCount === "number" && Number.isFinite(suspiciousCount)) {
    state.batchSuspiciousCounts[batchId] = suspiciousCount;
  }

  countEl.textContent = String(state.batchSuspiciousCounts[batchId] || 0);
}

/**
 * Increment suspicious count for a batch by one.
 * @param {string} batchId
 */
function incrementBatchSuspiciousCount(batchId) {
  const next = (state.batchSuspiciousCounts[batchId] || 0) + 1;
  updateBatchStatus(batchId, document.getElementById(`batch-status-${batchId}`)?.textContent || "running", next);
}

// -----------------------------------------------------------------------------
// Activity log panel
// -----------------------------------------------------------------------------

/**
 * Add one log line in timestamp order (append).
 * @param {string} message
 */
function addLogEntry(message) {
  if (!ui.activityLog) {
    console.log(`[FraudDetection] ${message}`);
    return;
  }

  const firstLine = ui.activityLog.querySelector(".log-entry");
  if (firstLine && firstLine.textContent?.includes("Waiting for events")) {
    ui.activityLog.innerHTML = "";
  }

  const line = document.createElement("p");
  line.className = "log-entry";
  line.textContent = `[${nowTime()}] ${message}`;

  ui.activityLog.appendChild(line);
  ui.activityLog.scrollTop = ui.activityLog.scrollHeight;
}

// -----------------------------------------------------------------------------
// Suspicious transaction panel
// -----------------------------------------------------------------------------

/**
 * Add one suspicious transaction card to the UI.
 * @param {Object} record
 */
function addSuspiciousCard(record) {
  if (!ui.suspiciousList) {
    return;
  }

  const key = suspiciousKey(record);
  if (state.seenSuspiciousKeys.has(key)) {
    return;
  }
  state.seenSuspiciousKeys.add(key);

  if (ui.suspiciousEmpty) {
    ui.suspiciousEmpty.remove();
  }

  const reasons = Array.isArray(record.reasons) && record.reasons.length > 0
    ? record.reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")
    : "<li>n/a</li>";

  const amountText = Number.isFinite(Number(record.amount))
    ? `$${Number(record.amount).toFixed(2)}`
    : "n/a";

  const scoreText = Number.isFinite(Number(record.risk_score))
    ? Number(record.risk_score).toFixed(2)
    : "n/a";

  const card = document.createElement("article");
  card.className = "txn-card";
  card.innerHTML = `
    <h3>${escapeHtml(record.id || "unknown")}</h3>
    <div class="txn-fields">
      <div><strong>Amount:</strong> ${escapeHtml(amountText)}</div>
      <div><strong>Merchant:</strong> ${escapeHtml(record.merchant || "n/a")}</div>
      <div><strong>Location:</strong> ${escapeHtml(record.location || "n/a")}</div>
      <div><strong>Channel:</strong> ${escapeHtml(record.channel || "n/a")}</div>
      <div><strong>Risk Score:</strong> ${escapeHtml(scoreText)}</div>
      <div><strong>Batch:</strong> ${escapeHtml(record.batch_id || "n/a")}</div>
    </div>
    <div style="margin-top: 0.45rem;">
      <strong>Reasons:</strong>
      <ul style="margin: 0.3rem 0 0 1rem; padding: 0;">${reasons}</ul>
    </div>
  `;

  // Newest first
  ui.suspiciousList.prepend(card);
}

/**
 * Reset suspicious panel for a new run.
 */
function clearSuspiciousPanel() {
  if (!ui.suspiciousList) {
    return;
  }

  ui.suspiciousList.innerHTML = "";
  const empty = document.createElement("p");
  empty.className = "empty";
  empty.id = "suspicious-empty";
  empty.textContent = "No suspicious transactions yet.";
  ui.suspiciousList.appendChild(empty);
  ui.suspiciousEmpty = empty;
  state.seenSuspiciousKeys.clear();
}

/**
 * Fetch existing suspicious transactions from backend and render them.
 */
async function restoreSuspiciousRecords() {
  try {
    const response = await fetch("/suspicious");
    if (!response.ok) {
      return;
    }

    const payload = await response.json();
    const records = Array.isArray(payload.suspicious_transactions)
      ? payload.suspicious_transactions
      : [];

    if (records.length === 0) {
      return;
    }

    // Oldest-to-newest from file; render newest on top by iterating in order and prepend.
    records.forEach((record) => {
      addSuspiciousCard(record);
      if (record.batch_id && BATCH_IDS.includes(record.batch_id)) {
        incrementBatchSuspiciousCount(record.batch_id);
      }
    });

    addLogEntry(`Restored ${records.length} suspicious transaction(s) from state.`);
  } catch (error) {
    addLogEntry(`Could not restore previous suspicious transactions: ${error}`);
  }
}

// -----------------------------------------------------------------------------
// SSE handling
// -----------------------------------------------------------------------------

/**
 * Handle one incoming event object from SSE.
 * @param {{type?: string, batch_id?: string, message?: string, suspicious_count?: number, transaction?: Object}} event
 */
function handleEvent(event) {
  const type = event.type || "unknown";
  const batchId = event.batch_id;

  switch (type) {
    case "batch_started": {
      if (batchId) {
        updateBatchStatus(batchId, "running");
      }
      addLogEntry(event.message || `${batchId} started`);
      break;
    }

    case "batch_completed": {
      if (batchId) {
        const count = Number(event.suspicious_count);
        const safeCount = Number.isFinite(count) ? count : state.batchSuspiciousCounts[batchId] || 0;
        updateBatchStatus(batchId, "completed", safeCount);
      }
      addLogEntry(event.message || `${batchId} completed`);
      break;
    }

    case "agent_started":
    case "agent_completed":
    case "tool_called": {
      addLogEntry(event.message || `${type} (${batchId || "n/a"})`);
      break;
    }

    case "suspicious_added": {
      const transaction = event.transaction || {};
      addSuspiciousCard(transaction);
      if (batchId && BATCH_IDS.includes(batchId)) {
        incrementBatchSuspiciousCount(batchId);
      }
      addLogEntry(event.message || `Suspicious transaction added in ${batchId}`);
      break;
    }

    case "error": {
      addLogEntry(`ERROR: ${event.message || "unknown error"}`);
      if (batchId && BATCH_IDS.includes(batchId)) {
        updateBatchStatus(batchId, "completed");
      }
      break;
    }

    case "run_completed": {
      state.isRunning = false;
      ui.startButton.disabled = false;
      ui.runStatus.textContent = "Completed";
      addLogEntry(event.message || "Run completed");
      break;
    }

    default: {
      addLogEntry(`Unhandled event: ${type}`);
      break;
    }
  }
}

/**
 * Open (or reopen) SSE connection.
 */
function connectEventStream() {
  if (state.eventSource) {
    state.eventSource.close();
  }

  const source = new EventSource("/events");
  state.eventSource = source;

  source.onopen = () => {
    addLogEntry("Connected to live event stream.");
  };

  source.onmessage = (rawEvent) => {
    try {
      const parsed = JSON.parse(rawEvent.data);
      handleEvent(parsed);
    } catch (error) {
      addLogEntry(`Failed to parse SSE event: ${error}`);
    }
  };

  source.onerror = () => {
    addLogEntry("Event stream connection issue. Browser will retry automatically.");
  };
}

// -----------------------------------------------------------------------------
// Demo start flow
// -----------------------------------------------------------------------------

/**
 * Send POST /start-demo and start one full run.
 */
async function startDemo() {
  if (state.isRunning) {
    addLogEntry("A demo run is already in progress.");
    return;
  }

  state.isRunning = true;
  if (ui.startButton) {
    ui.startButton.disabled = true;
  }
  if (ui.runStatus) {
    ui.runStatus.textContent = "Starting...";
  }

  // Reset visual state for a fresh run.
  initBatchCards();
  clearSuspiciousPanel();
  addLogEntry("Starting demo run...");

  try {
    const response = await fetch("/start-demo", {
      method: "POST",
    });

    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(payload.message || `Request failed (${response.status})`);
    }

    if (ui.runStatus) {
      ui.runStatus.textContent = "Running";
    }
    addLogEntry(payload.message || "Demo started.");
  } catch (error) {
    state.isRunning = false;
    if (ui.startButton) {
      ui.startButton.disabled = false;
    }
    if (ui.runStatus) {
      ui.runStatus.textContent = "Error";
    }
    addLogEntry(`Failed to start demo: ${error}`);
  }
}

// -----------------------------------------------------------------------------
// Page bootstrap
// -----------------------------------------------------------------------------

function attachEventHandlers() {
  if (ui.startButton) {
    ui.startButton.addEventListener("click", startDemo);
  } else {
    console.warn("[FraudDetection] Start button not found in DOM.");
  }
}

function bootstrap() {
  if (!ui.activityLog || !ui.suspiciousList) {
    console.warn("[FraudDetection] Some expected DOM elements were not found. Check templates/index.html IDs.");
  }

  initBatchCards();
  attachEventHandlers();
  connectEventStream();
  restoreSuspiciousRecords();
}

// Backward-compatibility global handlers (useful if an old HTML template uses inline onclick)
window.startDemo = startDemo;
window.startAnalysis = startDemo;

document.addEventListener("DOMContentLoaded", bootstrap);
