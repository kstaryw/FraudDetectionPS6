# FraudDetection PS-6

## Project Overview
FraudDetection PS-6 is a FastAPI + vanilla JavaScript demo that detects suspicious transactions from a dataset that is larger than a single LLM context window. The app processes transactions in chunks, runs batch analysis in parallel with asynchronous calls, stores suspicious results in a JSONL accumulator file, and streams progress to the UI in near real time using Server-Sent Events (SSE).

## Architecture Summary
The system has four main parts:

1. **Data generation**
   - `generate_transactions.py` creates exactly 100 synthetic transactions.
   - Includes seeded suspicious examples via `isSeedFraud` for verification.

2. **Batch fraud analysis**
   - `fraud_agent.py` exposes `analyze_batch(batch_id, transactions)`.
   - Sends one batch to the OpenAI API with strict prompt constraints.
   - Returns structured JSON with suspicious IDs, risk score, and reasons.

3. **Pipeline + state + events**
   - `app.py` orchestrates the run:
     - loads transaction file
     - chunks into 5 batches of 20
     - processes all batches concurrently with `asyncio.gather`
     - appends suspicious records to JSONL state
     - publishes live events to SSE clients
   - `tools.py` provides reusable utility functions:
     - chunking
     - lock-safe JSONL append
     - state reset/load
     - event payload builder
     - in-memory event pub/sub stream

4. **Frontend dashboard**
   - `templates/index.html` provides the dashboard layout.
   - `static/app.js` starts the demo, listens to `/events`, updates batch status, activity log, and suspicious transaction cards live.

## Folder Structure

```text
FraudDetectionPS6/
├── app.py
├── generate_transactions.py
├── fraud_agent.py
├── tools.py
├── data/
│   ├── sampleData.json
│   ├── suspiciousTransactions.json
│   └── transactions_100.json
├── state/
│   └── suspicious_transactions.jsonl
├── templates/
│   └── index.html
├── static/
│   └── app.js
├── requirements.txt
└── README.md
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

Expected `requirements.txt` packages:
- fastapi
- uvicorn
- jinja2
- python-multipart
- openai

## Set OPENAI_API_KEY

### Linux / macOS
```bash
export OPENAI_API_KEY="your_api_key_here"
```

### Windows (PowerShell)
```powershell
$env:OPENAI_API_KEY="your_api_key_here"
```

## Generate Sample Transactions

```bash
python generate_transactions.py
```

This creates:
- `data/transactions_100.json` (exactly 100 records)
- seeded suspicious transactions for testing (`isSeedFraud: true`)

## Run the FastAPI App

```bash
uvicorn app:app --reload
```

Then open:
- `http://localhost:8000`

Click **Start Demo** to launch the fraud detection pipeline.

## API Endpoints

- `GET /`
  - Serves dashboard page (`templates/index.html`).

- `POST /start-demo`
  - Resets `state/suspicious_transactions.jsonl`
  - Loads `data/transactions_100.json`
  - Chunks into 5 batches of 20
  - Runs all batches in parallel
  - Returns immediately so UI stays responsive

- `GET /events`
  - SSE endpoint streaming live events.

- `GET /suspicious`
  - Returns current suspicious records from JSONL accumulator.

## What the UI Shows

1. **Batch Status**
   - `batch_1` to `batch_5`
   - current status (`pending`, `running`, `completed`)
   - suspicious count per batch

2. **Agent and Tool Activity Log**
   - live log entries from SSE events in timestamp order
   - event types include:
     - `batch_started`
     - `batch_completed`
     - `agent_started`
     - `agent_completed`
     - `tool_called`
     - `suspicious_added`
     - `error`

3. **Suspicious Transactions**
   - near real-time cards as suspicious records are found
   - card fields:
     - transaction id
     - amount
     - merchant
     - location
     - channel
     - risk score
     - reasons

## Core Concepts

### Chunking
Transactions are split using `chunk_transactions(transactions, 20)` so each LLM call handles one manageable batch.

### Parallel Processing
All five batches are processed concurrently with `asyncio.gather(...)` to reduce overall run time.

### Accumulator State (JSONL)
Each suspicious record is appended to:
- `state/suspicious_transactions.jsonl`

This file acts as app state and can be reloaded by the UI (`GET /suspicious`). Writes are protected by an asyncio lock to avoid race conditions.

### Live Updates
The backend publishes events into an in-memory event manager, and the frontend consumes them through SSE (`/events`) for near real-time status/log/transaction updates.

## Assignment Satisfaction Checklist

This implementation satisfies the assignment requirements:

- ✅ **100 transactions**
  - generated and stored in `data/transactions_100.json`

- ✅ **5 batches of 20**
  - chunking function creates five fixed-size batches

- ✅ **parallel LLM calls**
  - batches run concurrently via async tasks + `asyncio.gather`

- ✅ **suspicious transaction accumulator file**
  - every suspicious result appended to `state/suspicious_transactions.jsonl`

- ✅ **near real-time UI**
  - SSE stream updates dashboard as events occur

- ✅ **monitoring of agent and tool calls**
  - activity log receives `agent_*` and `tool_called` events

## Quick Run (Codespaces)

```bash
pip install -r requirements.txt
export OPENAI_API_KEY="your_api_key_here"
python generate_transactions.py
uvicorn app:app --reload
```

Open the forwarded port for `localhost:8000` and click **Start Demo**.
