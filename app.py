"""
FastAPI backend for fraud detection system.
Handles transaction batch processing and SSE streaming to frontend.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from fraud_agent import analyze_transaction_batch, validate_transaction_id
from generate_transactions import generate_transactions, save_transactions


# Models
class AnalysisRequest(BaseModel):
    """Request model for fraud analysis"""
    num_transactions: int = 100
    num_batches: int = 5


# State
class AppState:
    """Application state"""
    def __init__(self):
        self.suspicious_transactions: list[str] = []
        self.all_transactions: list[dict] = []
        self.state_file = Path("state/suspicious_transactions.jsonl")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.events_queue: list[dict] = []
        self.lock = asyncio.Lock()
    
    async def append_suspicious(self, transaction_id: str) -> None:
        """Append a suspicious transaction ID to the JSONL file"""
        async with self.lock:
            # Validate ID
            if not validate_transaction_id(transaction_id, self.all_transactions):
                print(f"⚠ Invalid transaction ID: {transaction_id}")
                return
            
            # Append to file
            with open(self.state_file, 'a') as f:
                f.write(json.dumps({"transaction_id": transaction_id, "timestamp": asyncio.get_event_loop().time()}) + '\n')
            
            self.suspicious_transactions.append(transaction_id)
    
    async def emit_event(self, event_type: str, data: dict) -> None:
        """Emit an event to all connected clients"""
        async with self.lock:
            event = {"type": event_type, "data": data}
            self.events_queue.append(event)
    
    def get_and_clear_events(self) -> list[dict]:
        """Get all pending events and clear the queue"""
        events = self.events_queue[:]
        self.events_queue.clear()
        return events
    
    def reset(self) -> None:
        """Reset state"""
        self.suspicious_transactions = []
        self.all_transactions = []
        self.events_queue = []
        # Clear state file
        if self.state_file.exists():
            self.state_file.unlink()


# Create state
app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager"""
    print("🚀 Fraud Detection API starting...")
    yield
    print("🛑 Fraud Detection API stopping...")


# Create FastAPI app
app = FastAPI(
    title="Fraud Detection API",
    description="Parallel batch fraud detection with LLM analysis",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# Event streaming
async def event_stream() -> AsyncGenerator[str, None]:
    """
    Server-Sent Events stream that sends updates to frontend.
    Yields events in SSE format.
    """
    while True:
        events = app_state.get_and_clear_events()
        
        for event in events:
            event_json = json.dumps(event)
            yield f"data: {event_json}\n\n"
        
        await asyncio.sleep(0.5)


# Routes
@app.get("/")
async def root():
    """Serve the frontend HTML"""
    return FileResponse("templates/index.html")


@app.post("/api/analyze")
async def analyze_fraud(request: AnalysisRequest):
    """
    Main endpoint: Generate transactions and analyze them in parallel batches.
    
    Args:
        request: Analysis request with num_transactions and num_batches
    
    Returns:
        Summary of analysis results
    """
    try:
        # Reset state
        app_state.reset()
        
        # Generate transactions
        print(f"\n📊 Generating {request.num_transactions} transactions...")
        transactions = generate_transactions(request.num_transactions)
        app_state.all_transactions = transactions
        
        # Save to file
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        with open(data_dir / "transactions_100.json", "w") as f:
            json.dump(transactions, f, indent=2)
        
        await app_state.emit_event("status", {
            "message": f"Generated {request.num_transactions} transactions",
            "total_transactions": request.num_transactions,
        })
        
        # Split into batches
        batch_size = request.num_transactions // request.num_batches
        batches = [
            transactions[i:i+batch_size]
            for i in range(0, request.num_transactions, batch_size)
        ][:request.num_batches]
        
        print(f"📦 Split into {len(batches)} batches of ~{batch_size} transactions each")
        await app_state.emit_event("batch_count", {"count": len(batches)})
        
        # Process batches in parallel
        print("\n🔍 Analyzing batches in parallel...")
        
        async def process_batch(batch_num: int, batch: list[dict]) -> tuple[list[str], list[dict]]:
            """Process a single batch"""
            print(f"  → Batch {batch_num}: Processing {len(batch)} transactions...")
            
            await app_state.emit_event("batch_status", {
                "batch": batch_num,
                "status": "processing",
                "transaction_count": len(batch),
            })
            
            try:
                suspicious_ids, details = await analyze_transaction_batch(batch_num, batch)
                
                # Emit activity log entry
                await app_state.emit_event("activity", {
                    "batch": batch_num,
                    "message": f"Analyzed {len(batch)} transactions, found {len(suspicious_ids)} suspicious",
                    "suspicious_count": len(suspicious_ids),
                })
                
                # Add suspicious transactions to state
                for txn_id in suspicious_ids:
                    await app_state.append_suspicious(txn_id)
                    
                    # Find transaction details
                    txn = next((t for t in batch if t["id"] == txn_id), None)
                    if txn:
                        await app_state.emit_event("suspicious_transaction", {
                            "id": txn_id,
                            "amount": txn["amount"],
                            "merchant": txn["merchant"],
                            "category": txn["category"],
                            "batch": batch_num,
                        })
                
                await app_state.emit_event("batch_status", {
                    "batch": batch_num,
                    "status": "completed",
                    "suspicious_count": len(suspicious_ids),
                })
                
                return suspicious_ids, details
            
            except Exception as e:
                print(f"  ✗ Error processing batch {batch_num}: {str(e)}")
                await app_state.emit_event("batch_status", {
                    "batch": batch_num,
                    "status": "error",
                    "error": str(e),
                })
                return [], []
        
        # Run all batches concurrently
        results = await asyncio.gather(
            *[process_batch(i, batch) for i, batch in enumerate(batches)],
            return_exceptions=False,
        )
        
        # Aggregate results
        all_suspicious = []
        all_details = []
        for suspicious_ids, details in results:
            all_suspicious.extend(suspicious_ids)
            all_details.extend(details)
        
        print(f"\n✅ Analysis complete!")
        print(f"   Total suspicious transactions: {len(all_suspicious)}")
        print(f"   State file: {app_state.state_file}")
        
        await app_state.emit_event("analysis_complete", {
            "total_suspicious": len(all_suspicious),
            "total_analyzed": request.num_transactions,
            "suspicious_percentage": round(100 * len(all_suspicious) / request.num_transactions, 2),
        })
        
        return {
            "status": "success",
            "total_transactions": request.num_transactions,
            "total_batches": len(batches),
            "suspicious_count": len(all_suspicious),
            "suspicious_percentage": round(100 * len(all_suspicious) / request.num_transactions, 2),
        }
    
    except Exception as e:
        print(f"✗ Analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/events")
async def get_events():
    """
    SSE endpoint for real-time event streaming.
    Returns a continuous stream of Server-Sent Events.
    """
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
    )


@app.get("/api/suspicious")
async def get_suspicious_transactions():
    """
    Fetch all currently flagged suspicious transactions.
    
    Returns:
        List of transaction IDs flagged as suspicious
    """
    return {
        "suspicious_transactions": app_state.suspicious_transactions,
        "total_count": len(app_state.suspicious_transactions),
    }


@app.get("/api/state")
async def get_state():
    """
    Fetch current application state.
    
    Returns:
        Current state including suspicious transactions count
    """
    return {
        "suspicious_count": len(app_state.suspicious_transactions),
        "all_transactions_count": len(app_state.all_transactions),
        "state_file": str(app_state.state_file),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
