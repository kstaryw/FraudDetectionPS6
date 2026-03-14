"""Simple local pipeline test runner for FraudDetection PS-6.

Run:
    python test_pipeline.py

Optional flags:
    python test_pipeline.py --all
    python test_pipeline.py --batch 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from fraud_agent import analyze_batch
from tools import chunk_transactions


DATA_PATH = Path("data/transactions_100.json")
BATCH_SIZE = 20


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for selecting which batches to test."""
    parser = argparse.ArgumentParser(description="Local fraud pipeline test utility")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Analyze all 5 batches (default analyzes only batch 1)",
    )
    parser.add_argument(
        "--batch",
        type=int,
        choices=range(1, 6),
        metavar="{1,2,3,4,5}",
        help="Analyze one specific batch number (1-5)",
    )
    return parser.parse_args()


def load_transactions(path: Path = DATA_PATH) -> list[dict[str, Any]]:
    """Load transactions from JSON file."""
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run 'python generate_transactions.py' first."
        )
    with path.open("r", encoding="utf-8") as file_handle:
        data = json.load(file_handle)

    if not isinstance(data, list):
        raise ValueError("Transaction file must contain a JSON array.")

    return data


def validate_ids_in_batch(
    suspicious: list[dict[str, Any]],
    batch: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    """Return (valid_ids, invalid_ids) for suspicious IDs compared to one batch."""
    batch_ids = {str(txn.get("id")) for txn in batch if txn.get("id")}
    valid_ids: list[str] = []
    invalid_ids: list[str] = []

    for item in suspicious:
        txn_id = str(item.get("id", ""))
        if txn_id in batch_ids:
            valid_ids.append(txn_id)
        else:
            invalid_ids.append(txn_id)

    return valid_ids, invalid_ids


def compare_with_seeded_fraud(
    suspicious_ids: list[str],
    batch: list[dict[str, Any]],
) -> dict[str, int]:
    """Compare flagged results to seeded fraud labels in the batch."""
    seeded_ids = {txn["id"] for txn in batch if txn.get("isSeedFraud") is True}
    flagged_set = set(suspicious_ids)

    return {
        "seeded_in_batch": len(seeded_ids),
        "flagged": len(flagged_set),
        "flagged_seeded": len(flagged_set & seeded_ids),
        "missed_seeded": len(seeded_ids - flagged_set),
        "flagged_not_seeded": len(flagged_set - seeded_ids),
    }


def print_batch_sizes(batches: list[list[dict[str, Any]]]) -> None:
    """Print each batch size for a quick chunking sanity check."""
    print("\nBatch size summary:")
    for index, batch in enumerate(batches, start=1):
        print(f"  batch_{index}: {len(batch)} transactions")


async def run_batch(batch_number: int, batch: list[dict[str, Any]]) -> dict[str, Any]:
    """Execute analysis for one batch and print a clear result section."""
    batch_id = f"batch_{batch_number}"
    print(f"\n=== Running {batch_id} ===")

    result = await analyze_batch(batch_id, batch)
    suspicious = result.get("suspicious", [])

    if not isinstance(suspicious, list):
        suspicious = []

    valid_ids, invalid_ids = validate_ids_in_batch(suspicious, batch)

    print(f"Suspicious returned: {len(suspicious)}")
    print(f"Valid suspicious IDs: {len(valid_ids)}")
    print(f"Invalid suspicious IDs: {len(invalid_ids)}")

    if invalid_ids:
        print("Invalid IDs (should be none):")
        for txn_id in invalid_ids:
            print(f"  - {txn_id}")

    if suspicious:
        print("Flagged transactions:")
        for item in suspicious:
            txn_id = item.get("id", "unknown")
            risk_score = item.get("risk_score", 0)
            reasons = item.get("reasons", [])
            reason_text = ", ".join(str(reason) for reason in reasons) if reasons else "n/a"
            print(f"  - {txn_id} | risk_score={risk_score} | reasons=[{reason_text}]")
    else:
        print("No suspicious transactions returned for this batch.")

    seeded_compare = compare_with_seeded_fraud(valid_ids, batch)
    print("Seeded fraud comparison:")
    for key, value in seeded_compare.items():
        print(f"  {key}: {value}")

    return {
        "batch_id": batch_id,
        "returned": len(suspicious),
        "valid_ids": len(valid_ids),
        "invalid_ids": len(invalid_ids),
        **seeded_compare,
    }


async def main() -> None:
    """Load data, chunk it, and run analyzer on selected batches."""
    args = parse_args()

    transactions = load_transactions(DATA_PATH)
    batches = chunk_transactions(transactions, size=BATCH_SIZE)

    print(f"Loaded {len(transactions)} transactions from {DATA_PATH}")
    print_batch_sizes(batches)

    if len(batches) != 5 or any(len(batch) != 20 for batch in batches):
        print("Warning: expected 5 batches of 20 for this assignment.")

    if args.batch is not None:
        selected_batch_numbers = [args.batch]
    elif args.all:
        selected_batch_numbers = [1, 2, 3, 4, 5]
    else:
        selected_batch_numbers = [1]

    print(f"\nSelected batches: {', '.join(f'batch_{number}' for number in selected_batch_numbers)}")

    summaries: list[dict[str, Any]] = []
    for batch_number in selected_batch_numbers:
        batch = batches[batch_number - 1]
        summary = await run_batch(batch_number, batch)
        summaries.append(summary)

    print("\n=== Final Summary ===")
    total_returned = sum(item["returned"] for item in summaries)
    total_invalid = sum(item["invalid_ids"] for item in summaries)
    total_flagged_seeded = sum(item["flagged_seeded"] for item in summaries)
    total_seeded = sum(item["seeded_in_batch"] for item in summaries)

    print(f"Batches tested: {len(summaries)}")
    print(f"Total suspicious returned: {total_returned}")
    print(f"Total invalid IDs: {total_invalid}")
    print(f"Seeded detected: {total_flagged_seeded}/{total_seeded}")

    if total_invalid == 0:
        print("ID validation check: PASS")
    else:
        print("ID validation check: FAIL")


if __name__ == "__main__":
    asyncio.run(main())
