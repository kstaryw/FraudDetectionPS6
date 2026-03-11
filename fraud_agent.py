"""
Fraud detection agent that uses an LLM to analyze transaction batches.
Processes transactions with LangChain agents and tools.
"""

import json
import os
from typing import List, Dict, Any
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from tools import (
    check_transaction_amount,
    check_merchant_category,
    check_location_anomaly,
    summarize_transaction_risk,
)


def create_fraud_agent() -> AgentExecutor:
    """
    Create a fraud detection agent with tools.
    
    Returns:
        Initialized AgentExecutor with fraud detection tools
    """
    # Get API key from environment
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    # Initialize LLM
    llm = ChatOpenAI(
        model="gpt-4-turbo",
        temperature=0,
        api_key=api_key,
    )
    
    # Define tools
    tools = [
        check_transaction_amount,
        check_merchant_category,
        check_location_anomaly,
        summarize_transaction_risk,
    ]
    
    # Create prompt
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            """You are a fraud detection specialist analyzing financial transactions.
            
Your task is to evaluate each transaction and determine if it is suspicious.
Use the available tools to check:
1. Transaction amount (unusual amounts are suspicious)
2. Merchant-category combinations (some combinations are high-risk)
3. Location anomalies (unknown locations or mismatched card-present status)
4. Overall risk assessment combining all factors

For each transaction, you MUST provide a final decision:
- If risk score >= 5, the transaction is SUSPICIOUS
- If risk score < 5, the transaction is LEGITIMATE

Always include the transaction ID in your response."""
        ),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    # Create agent
    agent = create_tool_calling_agent(llm, tools, prompt)
    
    # Create executor
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
    )
    
    return executor


async def analyze_transaction_batch(
    batch_num: int,
    transactions: List[Dict[str, Any]],
) -> tuple[List[str], List[Dict[str, Any]]]:
    """
    Analyze a batch of transactions for fraud using the agent.
    
    Args:
        batch_num: Batch number for logging
        transactions: List of transactions to analyze
    
    Returns:
        Tuple of (suspicious_ids, detailed_results)
    """
    agent = create_fraud_agent()
    suspicious_ids = []
    detailed_results = []
    
    for txn in transactions:
        # Create analysis prompt
        txn_json = json.dumps(txn, indent=2)
        prompt = f"""Analyze this transaction for fraud:

{txn_json}

Check all risk factors using the available tools, then provide a final determination:
Is this transaction SUSPICIOUS or LEGITIMATE?
Include the transaction ID in your response."""
        
        try:
            # Run agent analysis
            result = agent.invoke({"input": prompt})
            
            response_text = result.get("output", "")
            
            # Extract decision from response
            is_suspicious = "SUSPICIOUS" in response_text.upper()
            
            detailed_results.append({
                "transaction_id": txn["id"],
                "batch": batch_num,
                "is_suspicious": is_suspicious,
                "analysis": response_text[:500],  # Store first 500 chars
            })
            
            if is_suspicious:
                suspicious_ids.append(txn["id"])
        
        except Exception as e:
            print(f"  ✗ Error analyzing {txn['id']}: {str(e)}")
            detailed_results.append({
                "transaction_id": txn["id"],
                "batch": batch_num,
                "is_suspicious": False,
                "analysis": f"Error: {str(e)}",
            })
    
    return suspicious_ids, detailed_results


def validate_transaction_id(transaction_id: str, all_transactions: List[Dict[str, Any]]) -> bool:
    """
    Validate that a transaction ID exists in the dataset.
    
    Args:
        transaction_id: ID to validate
        all_transactions: List of all available transactions
    
    Returns:
        True if ID is valid, False otherwise
    """
    valid_ids = {txn["id"] for txn in all_transactions}
    return transaction_id in valid_ids
