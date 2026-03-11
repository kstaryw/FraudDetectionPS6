# Fraud Detection System - PS-6

A sophisticated fraud detection system that analyzes financial transactions in parallel using LLM-powered agents. Detects suspicious transactions across 100 synthetically generated transactions split into 5 concurrent batches.

## Features

✅ **Parallel Batch Processing**: 100 transactions split into 5 batches of 20, processed concurrently with `asyncio.gather()`  
✅ **LLM-Powered Analysis**: Uses OpenAI GPT-4 with tool-calling agents to detect fraud patterns  
✅ **Real-Time Updates**: Server-Sent Events (SSE) stream live detection results to the frontend  
✅ **Activity Monitoring**: Tracks agent calls, tool usage, and batch progress  
✅ **Persistent State**: Suspicious transactions stored in JSONL format  
✅ **Interactive Dashboard**: HTML/JavaScript UI shows batch status and results in near real-time  

## Architecture

```
FraudDetection/
├── app.py                          # FastAPI backend with SSE streaming
├── generate_transactions.py        # Generate 100 synthetic transactions
├── fraud_agent.py                  # LangChain agent for fraud analysis
├── tools.py                        # Tools used by the fraud agent
├── data/
│   └── transactions_100.json      # Generated transaction data
├── state/
│   └── suspicious_transactions.jsonl  # Accumulated suspicious flagged transactions
├── templates/
│   └── index.html                 # Frontend UI
├── static/
│   └── app.js                     # Frontend JavaScript
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

## Setup

### Prerequisites

- Python 3.9+
- OpenAI API key

### Installation

1. **Clone and setup the project**:
   ```bash
   cd /workspaces/FraudDetectionPS6
   ```

2. **Create virtual environment** (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set your OpenAI API key**:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

### Running the Application

1. **Generate sample transactions**:
   ```bash
   python generate_transactions.py
   ```
   Creates `data/transactions_100.json` with 100 synthetic transactions.

2. **Start the FastAPI server**:
   ```bash
   python app.py
   ```
   Server runs on `http://localhost:8000`

3. **Open the frontend**:
   - Navigate to `http://localhost:8000` in your browser
   - Click "Start Analysis" to begin processing

## How It Works

### 1. Transaction Generation
`generate_transactions.py` creates 100 synthetic transactions with:
- Varying amounts ($5 - $9,999)
- Different merchants and categories
- ~15% intentionally suspicious patterns (high amounts, high-risk merchants)

### 2. Batch Processing
The FastAPI backend:
1. Loads 100 transactions
2. Splits them into 5 batches of 20
3. Processes all batches concurrently using `asyncio.gather()`

### 3. Fraud Analysis
`fraud_agent.py` uses a LangChain agent with tool-calling:
- **analyze_transaction_batch()**: Main fraud analysis function
- Uses tools from `tools.py`:
  - `check_transaction_amount()`: Flag unusually high amounts
  - `check_merchant_category()`: Identify high-risk merchant combos
  - `check_location_anomaly()`: Detect geographic red flags
  - `summarize_transaction_risk()`: Compute final risk score

### 4. Real-Time Streaming
The frontend connects via SSE to receive events:
- Batch processing status
- Activity logs (agent decisions)
- Suspicious transactions as they're detected
- Final analysis summary

### 5. State Persistence
Suspicious transactions are appended to `state/suspicious_transactions.jsonl`:
```json
{"transaction_id": "TXN-000015", "timestamp": 1234567890.123}
{"transaction_id": "TXN-000042", "timestamp": 1234567892.456}
```

## API Endpoints

### `POST /api/analyze`
Start fraud analysis
- **Request**: `{ "num_transactions": 100, "num_batches": 5 }`
- **Response**: Summary of analysis results
- **Events streamed via SSE**:
  - `status`: Analysis started
  - `batch_count`: Number of batches
  - `batch_status`: Batch processing updates
  - `activity`: Activity log entries
  - `suspicious_transaction`: Individual flagged transactions
  - `analysis_complete`: Final summary

### `GET /api/events` (SSE)
Server-Sent Events stream for live updates

### `GET /api/suspicious`
Retrieve all flagged suspicious transactions
- **Response**: `{ "suspicious_transactions": [...], "total_count": N }`

### `GET /api/state`
Get current application state

### `GET /`
Serve frontend HTML

## Frontend Features

The interactive dashboard shows:

1. **Key Metrics**
   - Total transactions analyzed
   - Number of suspicious transactions found
   - Detection rate percentage

2. **Batch Processing Status**
   - 5 batch indicators showing:
     - Current status (pending/processing/completed/error)
     - Number of suspicious transactions per batch
     - Real-time spinner animation during processing

3. **Activity Log**
   - Timestamped entries for all events
   - Color-coded by type (batch, suspicious, complete, error)
   - Last 50 entries kept in view

4. **Suspicious Transactions List**
   - Real-time appearance of flagged transactions
   - Shows transaction ID, amount, merchant, category, batch number
   - Ordered by detection time (most recent first)

## Customization

### Adjust Transaction Count
Edit `app.py` line in `AnalysisRequest`:
```python
num_transactions: int = 100  # Change this value
```

### Change Batch Count
Modify the `/api/analyze` request payload in `static/app.js`

### Adjust Fraud Thresholds
Edit `tools.py` function `summarize_transaction_risk()` to change risk scoring

### Change LLM Model
In `fraud_agent.py`, modify:
```python
llm = ChatOpenAI(model="gpt-4-turbo")  # Try other models
```

## Design Decisions

- **asyncio.gather()**: Processes all batches concurrently for maximum parallelism
- **SSE**: Provides efficient, real-time streaming without polling
- **JSONL Storage**: Append-only format perfect for log-like data accumulation
- **Tool-Calling Agent**: Lets the LLM intelligently choose which analysis tools to use
- **Validation**: All suspicious transaction IDs validated against source data
- **Modular Structure**: Easy to extend with additional tools or change the LLM provider

## Troubleshooting

**"OPENAI_API_KEY not set"**
- Set your API key: `export OPENAI_API_KEY="your-key"`

**"Transaction analysis fails"**
- Check that OpenAI API is accessible
- Verify API key has sufficient quota
- Check internet connection

**"Frontend doesn't update in real-time"**
- Ensure SSE connection is open (check browser DevTools Network tab)
- Verify FastAPI is running on port 8000
- Try a different browser if issues persist

## Performance Notes

- All 5 batches process in parallel (not sequentially)
- Each batch analysis takes ~10-30 seconds depending on OpenAI API latency
- Total runtime: ~30-60 seconds for full 100-transaction analysis
- Frontend receives updates every ~0.5 seconds via SSE

## License

See LICENSE file for details.

---

**Built for GitHub Codespaces** ✨


