"""
FastAPI backend for the Fraud Detection demo (PS-6).

Endpoints
---------
GET  /            → Serve the dashboard HTML page
POST /start-demo  → Reset state, load transactions, launch parallel batches
GET  /events      → SSE stream of real-time pipeline events
GET  /suspicious  → All suspicious transactions accumulated so far

Run with:
    uvicorn app:app --reload
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# Batch analysis: analyze_batch(batch_id, transactions) -> dict
from fraud_agent import analyze_batch

# Utility helpers from tools.py
from tools import (
    append_suspicious_transaction,
    build_activity_event,
    chunk_transactions,
    event_stream,           # async generator that yields dicts to one SSE consumer
    load_suspicious_transactions,
    publish_event,          # broadcast a dict to every connected SSE consumer
    reset_state_file,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATA_FILE = Path("data/transactions_100.json")
STATE_FILE = "state/suspicious_transactions.jsonl"


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure required folders exist before the server starts accepting requests."""
    Path("data").mkdir(exist_ok=True)
    Path("state").mkdir(exist_ok=True)
    Path("static").mkdir(exist_ok=True)
    print("✅ Fraud Detection API is ready.  Visit http://localhost:8000")
    yield
    print("🛑 Fraud Detection API stopped.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Fraud Detection API",
    description="Parallel batch fraud detection with LLM analysis and live SSE streaming.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve files from /static (app.js, CSS, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_transactions() -> list[dict]:
    """Read 100 transactions from disk; raise a helpful error if the file is missing."""
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"{DATA_FILE} not found. "
            "Run  python generate_transactions.py  first to create it."
        )
    with DATA_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)


async def _process_one_batch(batch_index: int, batch: list[dict]) -> None:
    """Run the full event-emitting pipeline for a single batch of transactions.

    Steps
    -----
    1. batch_started  — announce work is starting
    2. agent_started  — LLM call is about to be made
    3. analyze_batch  — send batch to OpenAI
    4. agent_completed — LLM returned results
    5. (per suspicious txn) validate ID → persist → tool_called → suspicious_added
    6. batch_completed — summary for this batch

    Errors are caught and published as "error" events so the rest of the
    pipeline (other batches) keeps running.
    """
    batch_id = f"batch_{batch_index + 1}"
    # Build a set of valid IDs so we can reject invented IDs from the model
    valid_ids: set[str] = {txn["id"] for txn in batch}

    # --- Step 1: batch started ---
    await publish_event(
        build_activity_event(
            "batch_started",
            batch_id,
            f"Batch {batch_index + 1} started — {len(batch)} transactions",
            {"transaction_count": len(batch)},
        )
    )

    # --- Step 2: agent (LLM) call starting ---
    await publish_event(
        build_activity_event(
            "agent_started",
            batch_id,
            f"Sending {batch_id} to the LLM for fraud analysis…",
        )
    )

    # --- Step 3: call the LLM agent ---
    try:
        result: dict[str, Any] = await analyze_batch(batch_id, batch)
    except Exception as exc:
        # Publish the error but do not propagate — let other batches finish
        await publish_event(
            build_activity_event(
                "error",
                batch_id,
                f"analyze_batch failed for {batch_id}: {exc}",
            )
        )
        return

    suspicious_items: list[dict[str, Any]] = result.get("suspicious", [])

    # --- Step 4: agent completed ---
    await publish_event(
        build_activity_event(
            "agent_completed",
            batch_id,
            f"LLM returned {len(suspicious_items)} suspicious item(s) for {batch_id}",
            {"suspicious_count": len(suspicious_items)},
        )
    )

    # --- Step 5: persist each valid suspicious transaction ---
    for item in suspicious_items:
        txn_id: str = item.get("id", "")

        # Validate: only accept IDs that exist in *this* batch
        if txn_id not in valid_ids:
            continue

        # Look up the original transaction record for richer storage
        original = next((t for t in batch if t["id"] == txn_id), {})

        record: dict[str, Any] = {
            "id": txn_id,
            "batch_id": batch_id,
            "risk_score": item.get("risk_score", 0.0),
            "reasons": item.get("reasons", []),
            # Carry forward fields from the source transaction
            "amount": original.get("amount"),
            "merchant": original.get("merchant"),
            "category": original.get("category"),
            "location": original.get("location"),
            "channel": original.get("channel"),
            "accountId": original.get("accountId"),
            "isSeedFraud": original.get("isSeedFraud", False),
        }

        # Write to the JSONL accumulator (lock-protected inside the helper)
        await append_suspicious_transaction(record, STATE_FILE)

        # Notify the frontend that the write tool was called
        await publish_event(
            build_activity_event(
                "tool_called",
                batch_id,
                f"Appended {txn_id} to suspicious_transactions.jsonl",
                {"transaction_id": txn_id},
            )
        )

        # Notify the frontend that a new suspicious record is ready to display
        await publish_event(
            build_activity_event(
                "suspicious_added",
                batch_id,
                f"{txn_id} flagged as suspicious (risk {item.get('risk_score', 0):.2f})",
                {"transaction": record},
            )
        )

    # --- Step 6: batch completed ---
    await publish_event(
        build_activity_event(
            "batch_completed",
            batch_id,
            f"Batch {batch_index + 1} complete — {len(suspicious_items)} suspicious found",
            {"suspicious_count": len(suspicious_items)},
        )
    )


async def _run_pipeline() -> None:
    """Load transactions, split into 5 batches, and process all batches in parallel."""
    transactions = _load_transactions()

    # chunk_transactions(transactions, 20) → [[txn×20], [txn×20], …]
    batches = chunk_transactions(transactions, size=20)

    # asyncio.gather runs all 5 coroutines concurrently
    await asyncio.gather(
        *[_process_one_batch(i, batch) for i, batch in enumerate(batches)]
    )

    # Final summary broadcast once every batch is done
    total = len(load_suspicious_transactions(STATE_FILE))
    await publish_event(
        build_activity_event(
            "run_completed",
            "all",
            f"Pipeline complete — {total} suspicious transactions found across "
            f"{len(transactions)} total",
            {
                "total_suspicious": total,
                "total_transactions": len(transactions),
            },
        )
    )


# ---------------------------------------------------------------------------
# SSE formatter
# ---------------------------------------------------------------------------

async def _sse_stream() -> AsyncGenerator[str, None]:
    """Subscribe to the event bus and encode each dict as an SSE message.

    tools.event_stream() yields raw dicts; this wrapper encodes them into
    the  data: <json>\\n\\n  format that browsers expect.
    """
    async for event in event_stream():
        payload = json.dumps(event, ensure_ascii=False)
        yield f"data: {payload}\n\n"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", summary="Fraud detection dashboard")
async def dashboard():
    """Serve the HTML dashboard to the browser."""
    return FileResponse("templates/index.html")


@app.post("/start-demo", summary="Launch the fraud detection pipeline")
async def start_demo():
    """Reset state and start processing 5 transaction batches in parallel.

    Returns immediately; the browser receives live progress via GET /events.
    """
    # Wipe previous results so every run starts clean
    reset_state_file(STATE_FILE)

    # asyncio.create_task schedules the pipeline without blocking this response
    asyncio.create_task(_run_pipeline())

    return {
        "status": "started",
        "message": "Pipeline launched. Connect to /events for live updates.",
    }


@app.get("/events", summary="SSE live event stream")
async def events():
    """Stream real-time pipeline events to the browser using Server-Sent Events."""
    return StreamingResponse(
        _sse_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",       # prevent proxies from buffering
            "X-Accel-Buffering": "no",          # disable nginx buffering
        },
    )


@app.get("/suspicious", summary="All suspicious transactions so far")
async def suspicious():
    """Return every suspicious transaction currently in the JSONL accumulator."""
    records = load_suspicious_transactions(STATE_FILE)
    return {
        "count": len(records),
        "suspicious_transactions": records,
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    # Run directly:  python app.py
    # or:            uvicorn app:app --reload
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
