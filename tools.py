"""Utility helpers for chunking, state management, and SSE-style event broadcasting."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_FILE_DEFAULT = "state/suspicious_transactions.jsonl"


# Lock used by append_suspicious_transaction to prevent write races.
_state_file_lock = asyncio.Lock()


# In-memory pub/sub for SSE consumers.
_subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
_subscribers_lock = asyncio.Lock()


def chunk_transactions(transactions: list[dict], size: int = 20) -> list[list[dict]]:
    """Split transactions into fixed-size chunks.

    Args:
        transactions: Full transaction list.
        size: Chunk size. Defaults to 20.

    Returns:
        List of transaction batches.
    """
    if size <= 0:
        raise ValueError("size must be greater than 0")

    return [transactions[index:index + size] for index in range(0, len(transactions), size)]


async def append_suspicious_transaction(
    record: dict,
    path: str = STATE_FILE_DEFAULT,
) -> None:
    """Append one suspicious transaction record as a JSONL line.

    The function uses an asyncio lock to avoid race conditions during
    concurrent writes from parallel batch workers.
    """
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps(record, ensure_ascii=False)

    async with _state_file_lock:
        with file_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")


def load_suspicious_transactions(path: str = STATE_FILE_DEFAULT) -> list[dict]:
    """Load all suspicious transaction records from a JSONL file."""
    file_path = Path(path)
    if not file_path.exists():
        return []

    records: list[dict] = []
    with file_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                records.append(parsed)
    return records


def reset_state_file(path: str = STATE_FILE_DEFAULT) -> None:
    """Clear the suspicious transaction accumulator for a fresh run."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("", encoding="utf-8")


def build_activity_event(
    event_type: str,
    batch_id: str,
    message: str,
    extra: dict | None = None,
) -> dict:
    """Build a standardized activity event payload for the frontend."""
    event: dict[str, Any] = {
        "type": event_type,
        "batch_id": batch_id,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if extra:
        event.update(extra)
    return event


async def publish_event(event: dict) -> None:
    """Publish an event to all active subscribers."""
    async with _subscribers_lock:
        subscribers = list(_subscribers)

    for queue in subscribers:
        await queue.put(event)


async def event_stream() -> AsyncGenerator[dict, None]:
    """Yield events for one connected consumer.

    Consumers can serialize yielded dictionaries as SSE payloads.
    """
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async with _subscribers_lock:
        _subscribers.add(queue)

    try:
        while True:
            event = await queue.get()
            yield event
    finally:
        async with _subscribers_lock:
            _subscribers.discard(queue)
