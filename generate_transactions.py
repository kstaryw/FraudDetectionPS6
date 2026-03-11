"""
Generate sample transaction data for fraud detection analysis.
Creates 100 synthetic transactions with varying amounts, merchants, and patterns.
"""

import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any


def generate_transactions(count: int = 100) -> List[Dict[str, Any]]:
    """
    Generate synthetic transaction data.
    
    Args:
        count: Number of transactions to generate (default: 100)
    
    Returns:
        List of transaction dictionaries with id, amount, merchant, timestamp, etc.
    """
    merchants = [
        "Amazon", "Walmart", "Target", "Best Buy", "Gas Station",
        "Coffee Shop", "Restaurant", "Hotel", "Airlines", "Pharmacy",
        "Grocery Store", "Movie Theater", "Gym", "Uber", "Lyft",
    ]
    
    categories = [
        "Shopping", "Food", "Travel", "Entertainment", "Utilities",
        "Gas", "Services", "Health", "Transportation"
    ]
    
    transactions = []
    start_date = datetime.now() - timedelta(days=30)
    
    for i in range(count):
        # Mix normal and suspicious patterns
        if random.random() < 0.15:  # ~15% suspicious
            # Suspicious pattern
            amount = random.uniform(1500, 9999)
            merchant = random.choice(["Casino", "Wire Transfer", "Overseas Store"])
            timestamp = start_date + timedelta(
                hours=random.randint(2, 8), minutes=random.randint(0, 59)
            )
        else:
            # Normal pattern
            amount = random.uniform(5, 500)
            merchant = random.choice(merchants)
            timestamp = start_date + timedelta(
                hours=random.randint(8, 20), minutes=random.randint(0, 59)
            )
        
        transaction = {
            "id": f"TXN-{i+1:06d}",
            "amount": round(amount, 2),
            "merchant": merchant,
            "category": random.choice(categories),
            "timestamp": timestamp.isoformat(),
            "location": random.choice(["USA", "Canada", "Mexico", "Unknown"]),
            "card_present": random.choice([True, False]),
        }
        transactions.append(transaction)
        start_date += timedelta(minutes=15)
    
    return transactions


def save_transactions(transactions: List[Dict[str, Any]], filepath: str) -> None:
    """
    Save transactions to a JSON file.
    
    Args:
        transactions: List of transaction dictionaries
        filepath: Path to save the JSON file
    """
    with open(filepath, 'w') as f:
        json.dump(transactions, f, indent=2)
    print(f"✓ Generated {len(transactions)} transactions and saved to {filepath}")


if __name__ == "__main__":
    transactions = generate_transactions(100)
    save_transactions(transactions, "data/transactions_100.json")
