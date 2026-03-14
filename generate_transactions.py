"""Generate a realistic 100-transaction dataset with seeded fraud cases."""

from __future__ import annotations

import json
import random
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


TOTAL_TRANSACTIONS = 100
BATCH_SIZE = 20
SEEDED_FRAUD_PER_BATCH = 3
OUTPUT_PATH = Path("data/transactions_100.json")


@dataclass(frozen=True)
class MerchantProfile:
    """Merchant metadata used to generate realistic transactions."""

    name: str
    category: str
    amount_range: tuple[float, float]
    preferred_channels: tuple[str, ...]
    locations: tuple[str, ...]


NORMAL_MERCHANTS: tuple[MerchantProfile, ...] = (
    MerchantProfile("Amazon", "retail", (18.0, 420.0), ("card_not_present",), ("Seattle, USA", "Boston, USA")),
    MerchantProfile("Walmart", "groceries", (24.0, 260.0), ("card_present",), ("Dallas, USA", "Miami, USA")),
    MerchantProfile("Target", "retail", (20.0, 220.0), ("card_present", "card_not_present"), ("Chicago, USA", "Denver, USA")),
    MerchantProfile("Shell", "fuel", (35.0, 90.0), ("card_present",), ("Austin, USA", "Phoenix, USA")),
    MerchantProfile("Starbucks", "dining", (6.0, 22.0), ("card_present", "mobile_wallet"), ("Boston, USA", "San Diego, USA")),
    MerchantProfile("Uber", "transport", (11.0, 65.0), ("mobile_wallet", "card_not_present"), ("New York, USA", "San Francisco, USA")),
    MerchantProfile("Netflix", "subscription", (12.0, 28.0), ("card_not_present",), ("Los Gatos, USA",)),
    MerchantProfile("Delta Airlines", "travel", (180.0, 850.0), ("card_not_present",), ("Atlanta, USA", "Seattle, USA")),
    MerchantProfile("CVS", "health", (8.0, 70.0), ("card_present",), ("Boston, USA", "Providence, USA")),
    MerchantProfile("Whole Foods", "groceries", (24.0, 180.0), ("card_present", "mobile_wallet"), ("Boston, USA", "Portland, USA")),
)


SUSPICIOUS_MERCHANTS: tuple[MerchantProfile, ...] = (
    MerchantProfile("Bitcrypt Exchange", "crypto_exchange", (2400.0, 9800.0), ("online_transfer",), ("Tallinn, Estonia", "Vilnius, Lithuania")),
    MerchantProfile("Velvet Luxe", "luxury_goods", (1800.0, 7200.0), ("card_not_present",), ("Dubai, UAE", "Milan, Italy")),
    MerchantProfile("Oceanic Wire", "wire_transfer", (3000.0, 12000.0), ("online_transfer",), ("Hong Kong, China", "Singapore")),
    MerchantProfile("RareTimepieces", "luxury_goods", (2200.0, 8800.0), ("card_not_present",), ("Geneva, Switzerland", "Paris, France")),
)


KNOWN_LOCATIONS: tuple[str, ...] = (
    "Boston, USA",
    "Chicago, USA",
    "Seattle, USA",
    "Austin, USA",
    "Denver, USA",
    "San Francisco, USA",
    "New York, USA",
    "Toronto, Canada",
)

UNUSUAL_LOCATIONS: tuple[str, ...] = (
    "Lagos, Nigeria",
    "Moscow, Russia",
    "Dubai, UAE",
    "Tallinn, Estonia",
    "Bangkok, Thailand",
)

CHANNELS: tuple[str, ...] = (
    "card_present",
    "card_not_present",
    "mobile_wallet",
    "online_transfer",
)


def isoformat_z(timestamp: datetime) -> str:
    """Return an ISO 8601 UTC timestamp with a trailing Z."""

    return timestamp.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def choose_amount(rng: random.Random, amount_range: tuple[float, float]) -> float:
    """Pick a realistic amount rounded to cents."""

    return round(rng.uniform(*amount_range), 2)


def build_account_devices(account_ids: list[str]) -> dict[str, list[str]]:
    """Assign a small pool of recurring devices to each account."""

    return {
        account_id: [f"dev_{account_id[-3:]}_{index:02d}" for index in range(1, 4)]
        for account_id in account_ids
    }


def build_normal_transaction(
    txn_index: int,
    account_id: str,
    timestamp: datetime,
    rng: random.Random,
    account_devices: dict[str, list[str]],
) -> dict[str, Any]:
    """Build a non-fraudulent transaction."""

    merchant = rng.choice(NORMAL_MERCHANTS)
    channel = rng.choice(merchant.preferred_channels)
    location = rng.choice(merchant.locations if merchant.locations else KNOWN_LOCATIONS)
    device_id = rng.choice(account_devices[account_id])

    if channel == "card_present":
        location = rng.choice(KNOWN_LOCATIONS)

    return {
        "id": f"txn_{txn_index:04d}",
        "accountId": account_id,
        "timestamp": isoformat_z(timestamp),
        "amount": choose_amount(rng, merchant.amount_range),
        "currency": "USD",
        "merchant": merchant.name,
        "category": merchant.category,
        "channel": channel,
        "location": location,
        "deviceId": device_id,
        "isSeedFraud": False,
    }


def build_seeded_fraud_transaction(
    txn_index: int,
    account_id: str,
    timestamp: datetime,
    rng: random.Random,
    account_devices: dict[str, list[str]],
) -> dict[str, Any]:
    """Build a transaction with intentionally suspicious traits."""

    merchant = rng.choice(SUSPICIOUS_MERCHANTS)
    suspicious_location = rng.choice(UNUSUAL_LOCATIONS + merchant.locations)
    suspicious_channel = rng.choice(("online_transfer", "card_not_present"))
    known_device = rng.choice(account_devices[account_id])
    new_device_suffix = rng.randint(100, 999)

    device_id = known_device if rng.random() < 0.2 else f"dev_new_{account_id[-3:]}_{new_device_suffix}"

    return {
        "id": f"txn_{txn_index:04d}",
        "accountId": account_id,
        "timestamp": isoformat_z(timestamp),
        "amount": choose_amount(rng, merchant.amount_range),
        "currency": "USD",
        "merchant": merchant.name,
        "category": merchant.category,
        "channel": suspicious_channel,
        "location": suspicious_location,
        "deviceId": device_id,
        "isSeedFraud": True,
    }


def generate_transactions(count: int = TOTAL_TRANSACTIONS, seed: int = 42) -> list[dict[str, Any]]:
    """Generate exactly ``count`` transactions with seeded fraud in each batch of 20."""

    if count != TOTAL_TRANSACTIONS:
        raise ValueError(f"This generator is configured to create exactly {TOTAL_TRANSACTIONS} transactions.")

    if count % BATCH_SIZE != 0:
        raise ValueError("Transaction count must be divisible by the batch size.")

    rng = random.Random(seed)
    account_ids = [f"acc_{index:03d}" for index in range(1, 13)]
    account_devices = build_account_devices(account_ids)
    base_time = datetime(2026, 3, 9, 8, 15, tzinfo=timezone.utc)

    transactions: list[dict[str, Any]] = []

    for batch_start in range(0, count, BATCH_SIZE):
        fraud_offsets = set(rng.sample(range(BATCH_SIZE), SEEDED_FRAUD_PER_BATCH))
        current_time = base_time + timedelta(hours=batch_start // 2)

        for offset in range(BATCH_SIZE):
            txn_index = batch_start + offset + 1
            account_rotation = (batch_start // BATCH_SIZE) * 3 + offset
            account_id = account_ids[account_rotation % len(account_ids)]
            current_time += timedelta(minutes=rng.randint(7, 95))

            if offset in fraud_offsets:
                transaction = build_seeded_fraud_transaction(
                    txn_index=txn_index,
                    account_id=account_id,
                    timestamp=current_time,
                    rng=rng,
                    account_devices=account_devices,
                )
            else:
                transaction = build_normal_transaction(
                    txn_index=txn_index,
                    account_id=account_id,
                    timestamp=current_time,
                    rng=rng,
                    account_devices=account_devices,
                )

            transactions.append(transaction)

        base_time = current_time + timedelta(hours=3)

    return transactions


def save_transactions(transactions: list[dict[str, Any]], output_path: Path = OUTPUT_PATH) -> None:
    """Write generated transactions to disk as formatted JSON."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(transactions, handle, indent=2)


def summarize_transactions(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a compact summary of generated data for CLI output."""

    seeded_fraud_count = sum(1 for transaction in transactions if transaction["isSeedFraud"])
    account_count = len({transaction["accountId"] for transaction in transactions})
    category_counts = Counter(transaction["category"] for transaction in transactions)

    return {
        "total_transactions": len(transactions),
        "seeded_suspicious_transactions": seeded_fraud_count,
        "distinct_accounts": account_count,
        "top_categories": dict(category_counts.most_common(5)),
        "output_path": str(OUTPUT_PATH),
    }


def main() -> None:
    """Generate the dataset, save it, and print a summary."""

    transactions = generate_transactions()
    save_transactions(transactions)
    summary = summarize_transactions(transactions)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
