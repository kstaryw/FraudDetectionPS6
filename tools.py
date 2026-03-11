"""
Tool definitions for the fraud detection agent.
These tools help the agent analyze transactions for suspicious patterns.
"""

from typing import Dict, List, Any
from langchain.tools import tool
import json


@tool
def check_transaction_amount(amount: float) -> str:
    """
    Check if transaction amount is unusually high.
    
    Args:
        amount: Transaction amount in dollars
    
    Returns:
        Assessment of whether amount is suspicious
    """
    if amount > 1000:
        return f"SUSPICIOUS: Amount ${amount} exceeds typical transaction limit of $1000"
    elif amount > 500:
        return f"WARNING: Amount ${amount} is above average (typical range: $5-$500)"
    else:
        return f"NORMAL: Amount ${amount} is within typical range"


@tool
def check_merchant_category(merchant: str, category: str) -> str:
    """
    Check if merchant and category combination is suspicious.
    
    Args:
        merchant: Merchant name
        category: Transaction category
    
    Returns:
        Assessment of merchant-category combination
    """
    high_risk_merchants = {
        "Casino": ["Travel", "Entertainment"],
        "Wire Transfer": ["Travel", "Shopping"],
        "Overseas Store": ["Shopping", "Services"],
    }
    
    if merchant in high_risk_merchants:
        if category in high_risk_merchants[merchant]:
            return f"SUSPICIOUS: '{merchant}' + '{category}' is a high-risk combination"
        else:
            return f"HIGH RISK: Merchant '{merchant}' is inherently high-risk"
    
    return f"NORMAL: Merchant '{merchant}' is low-risk"


@tool
def check_location_anomaly(location: str, card_present: bool) -> str:
    """
    Check if location is anomalous.
    
    Args:
        location: Transaction location
        card_present: Whether card was physically present
    
    Returns:
        Assessment of location-based risk
    """
    if location == "Unknown":
        return "SUSPICIOUS: Location is unknown - cannot verify legitimacy"
    
    if location not in ["USA", "Canada"] and not card_present:
        return f"SUSPICIOUS: International transaction ({location}) without card present"
    
    return f"NORMAL: Location '{location}' appears legitimate"


@tool
def summarize_transaction_risk(transaction_data: str) -> str:
    """
    Summarize overall risk level for a transaction.
    Combines multiple risk factors.
    
    Args:
        transaction_data: JSON string of full transaction details
    
    Returns:
        Overall risk assessment
    """
    try:
        txn = json.loads(transaction_data)
        
        # Simple risk scoring
        risk_score = 0
        
        if txn.get("amount", 0) > 1000:
            risk_score += 3
        elif txn.get("amount", 0) > 500:
            risk_score += 1
        
        if txn.get("merchant") in ["Casino", "Wire Transfer", "Overseas Store"]:
            risk_score += 3
        
        if txn.get("location") == "Unknown":
            risk_score += 2
        
        if txn.get("location") not in ["USA", "Canada"] and not txn.get("card_present"):
            risk_score += 2
        
        if risk_score >= 5:
            return f"HIGH RISK: Risk score {risk_score}/10 - Transaction requires review"
        elif risk_score >= 3:
            return f"MEDIUM RISK: Risk score {risk_score}/10 - Potential concern"
        else:
            return f"LOW RISK: Risk score {risk_score}/10 - Appears legitimate"
    
    except Exception as e:
        return f"ERROR: Could not assess risk - {str(e)}"
