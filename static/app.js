/**
 * Fraud Detection Frontend
 * Real-time monitoring of batch processing and suspicious transaction detection
 */

// State
const state = {
    isAnalyzing: false,
    suspiciousTransactions: [],
    batchStatus: {},
    totalTransactions: 0,
};

// DOM Elements
const startBtn = document.getElementById('startBtn');
const activityLog = document.getElementById('activityLog');
const transactionsList = document.getElementById('transactionsList');
const batchIndicators = document.getElementById('batchIndicators');
const successMessage = document.getElementById('successMessage');

/**
 * Add entry to activity log
 * @param {string} message - Log message
 * @param {string} type - Log type: 'batch', 'suspicious', 'complete', 'error', 'info'
 */
function addLogEntry(message, type = 'info') {
    // Clear empty state if present
    if (activityLog.querySelector('.empty-state')) {
        activityLog.innerHTML = '';
    }

    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;

    const timestamp = new Date().toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
    });

    entry.innerHTML = `
        <span class="log-timestamp">${timestamp}</span>
        <span>${message}</span>
    `;

    activityLog.insertBefore(entry, activityLog.firstChild);

    // Keep only last 50 entries
    while (activityLog.children.length > 50) {
        activityLog.removeChild(activityLog.lastChild);
    }
}

/**
 * Add transaction to suspicious list
 * @param {Object} transaction - Transaction data
 */
function addSuspiciousTransaction(transaction) {
    // Clear empty state if present
    if (transactionsList.querySelector('.empty-state')) {
        transactionsList.innerHTML = '';
    }

    const item = document.createElement('div');
    item.className = 'transaction-item';

    item.innerHTML = `
        <div class="transaction-header">
            <span class="transaction-id">${transaction.id}</span>
            <span class="transaction-badge">SUSPICIOUS (Batch ${transaction.batch})</span>
        </div>
        <div class="transaction-details">
            <div class="transaction-detail">
                <span class="transaction-label">Amount:</span>
                <span class="transaction-value">$${transaction.amount.toFixed(2)}</span>
            </div>
            <div class="transaction-detail">
                <span class="transaction-label">Merchant:</span>
                <span class="transaction-value">${transaction.merchant}</span>
            </div>
            <div class="transaction-detail">
                <span class="transaction-label">Category:</span>
                <span class="transaction-value">${transaction.category}</span>
            </div>
        </div>
    `;

    transactionsList.insertBefore(item, transactionsList.firstChild);

    state.suspiciousTransactions.push(transaction.id);
    updateStats();
}

/**
 * Initialize batch indicators
 * @param {number} count - Number of batches
 */
function initBatchIndicators(count) {
    batchIndicators.innerHTML = '';
    state.batchStatus = {};

    for (let i = 0; i < count; i++) {
        const indicator = document.createElement('div');
        indicator.className = 'batch-indicator';
        indicator.id = `batch-${i}`;

        indicator.innerHTML = `
            <div class="batch-label">Batch ${i}</div>
            <div class="batch-status">
                <span class="spinner" id="batch-${i}-spinner"></span>
                <span id="batch-${i}-text">Pending</span>
            </div>
        `;

        batchIndicators.appendChild(indicator);
        state.batchStatus[i] = 'pending';
    }
}

/**
 * Update batch status
 * @param {number} batchNum - Batch number
 * @param {string} status - New status
 * @param {number} suspiciousCount - Number of suspicious transactions found
 */
function updateBatchStatus(batchNum, status, suspiciousCount = 0) {
    state.batchStatus[batchNum] = status;

    const indicator = document.getElementById(`batch-${batchNum}`);
    const text = document.getElementById(`batch-${batchNum}-text`);
    const spinner = document.getElementById(`batch-${batchNum}-spinner`);

    indicator.classList.remove('processing', 'completed', 'error');
    indicator.classList.add(status);

    if (status === 'processing') {
        spinner.style.display = 'inline-block';
        text.textContent = 'Processing...';
    } else if (status === 'completed') {
        spinner.style.display = 'none';
        text.textContent = `✓ Complete (${suspiciousCount} found)`;
    } else if (status === 'error') {
        spinner.style.display = 'none';
        text.textContent = '✗ Error';
    }
}

/**
 * Update statistics display
 */
function updateStats() {
    document.getElementById('totalTransactions').textContent = state.totalTransactions;
    document.getElementById('suspiciousCount').textContent = state.suspiciousTransactions.length;

    const rate = state.totalTransactions > 0
        ? Math.round((state.suspiciousTransactions.length / state.totalTransactions) * 100)
        : 0;
    document.getElementById('detectionRate').textContent = `${rate}%`;
}

/**
 * Show success message
 * @param {string} message - Message to display
 */
function showSuccess(message) {
    successMessage.innerHTML = `<div class="success-message">${message}</div>`;
    successMessage.style.display = 'block';

    setTimeout(() => {
        successMessage.style.display = 'none';
    }, 5000);
}

/**
 * Reset UI
 */
function resetUI() {
    state.isAnalyzing = false;
    state.suspiciousTransactions = [];
    state.batchStatus = {};
    state.totalTransactions = 0;

    activityLog.innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon">📋</div>
            <div>No activity yet. Click "Start Analysis" to begin.</div>
        </div>
    `;

    transactionsList.innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon">✓</div>
            <div>No suspicious transactions detected yet.</div>
        </div>
    `;

    batchIndicators.innerHTML = '';
    updateStats();

    startBtn.disabled = false;
    startBtn.textContent = '▶ Start Analysis';

    successMessage.style.display = 'none';
}

/**
 * Start fraud analysis
 */
async function startAnalysis() {
    if (state.isAnalyzing) return;

    state.isAnalyzing = true;
    startBtn.disabled = true;
    startBtn.textContent = '⏳ Analyzing...';

    resetUI();
    addLogEntry('Analysis started...', 'info');

    try {
        // Connect to SSE
        const eventSource = new EventSource('/api/events');

        eventSource.onmessage = (event) => {
            try {
                const { type, data } = JSON.parse(event.data);

                switch (type) {
                    case 'status':
                        addLogEntry(`📊 ${data.message}`, 'batch');
                        state.totalTransactions = data.total_transactions;
                        updateStats();
                        break;

                    case 'batch_count':
                        addLogEntry(`📦 Split into ${data.count} batches`, 'batch');
                        initBatchIndicators(data.count);
                        break;

                    case 'batch_status':
                        if (data.status === 'processing') {
                            addLogEntry(`🔄 Batch ${data.batch}: Processing ${data.transaction_count} transactions...`, 'batch');
                            updateBatchStatus(data.batch, 'processing');
                        } else if (data.status === 'completed') {
                            addLogEntry(`✓ Batch ${data.batch}: Found ${data.suspicious_count} suspicious transactions`, 'complete');
                            updateBatchStatus(data.batch, 'completed', data.suspicious_count);
                        } else if (data.status === 'error') {
                            addLogEntry(`✗ Batch ${data.batch}: Error - ${data.error}`, 'error');
                            updateBatchStatus(data.batch, 'error');
                        }
                        break;

                    case 'activity':
                        addLogEntry(`📋 Batch ${data.batch}: ${data.message}`, 'info');
                        addLogEntry(`🚨 Found ${data.suspicious_count} suspicious transactions in batch ${data.batch}`, 'suspicious');
                        break;

                    case 'suspicious_transaction':
                        addLogEntry(
                            `⚠️  Suspicious: ${data.id} - $${data.amount.toFixed(2)} at ${data.merchant} (Batch ${data.batch})`,
                            'suspicious'
                        );
                        addSuspiciousTransaction(data);
                        break;

                    case 'analysis_complete':
                        addLogEntry(`✅ Analysis Complete!`, 'complete');
                        addLogEntry(
                            `📈 Results: ${data.total_suspicious}/${data.total_analyzed} transactions flagged as suspicious (${data.suspicious_percentage}%)`,
                            'complete'
                        );
                        
                        showSuccess(
                            `✅ Analysis Complete! Found ${data.total_suspicious} suspicious transactions ` +
                            `out of ${data.total_analyzed} analyzed (${data.suspicious_percentage}%)`
                        );
                        
                        eventSource.close();
                        state.isAnalyzing = false;
                        startBtn.disabled = false;
                        startBtn.textContent = '▶ Start Analysis';
                        break;
                }
            } catch (e) {
                console.error('Error parsing event:', e);
            }
        };

        eventSource.onerror = (error) => {
            console.error('SSE Error:', error);
            if (eventSource.readyState === EventSource.CLOSED) {
                addLogEntry('Analysis connection closed', 'error');
            }
        };

        // Start analysis on backend
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                num_transactions: 100,
                num_batches: 5,
            }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Analysis failed');
        }

        const result = await response.json();
        console.log('Analysis result:', result);

    } catch (error) {
        console.error('Error:', error);
        addLogEntry(`✗ Error: ${error.message}`, 'error');
        state.isAnalyzing = false;
        startBtn.disabled = false;
        startBtn.textContent = '▶ Start Analysis';
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    addLogEntry('Ready for analysis', 'info');
});
