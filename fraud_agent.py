"""Batch fraud analysis helpers built on the OpenAI API."""

from __future__ import annotations

import importlib
import json
import os
from typing import Any


DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def empty_result(batch_id: str) -> dict[str, Any]:
    """Return the safe fallback shape used for all failures."""

    return {"batch_id": batch_id, "suspicious": []}


def build_prompt(batch_id: str, transactions: list[dict[str, Any]]) -> str:
    """Build a strict prompt that keeps the model grounded in the provided batch."""

    transaction_json = json.dumps(transactions, indent=2)
    return f"""
You are a fraud detection analyst.

Analyze exactly one batch of financial transactions and identify suspicious transactions.

Hard rules:
- Only use the transactions provided in this prompt.
- Do not invent transaction IDs, accounts, devices, merchants, timestamps, or reasons.
- Only include a transaction in the suspicious list if its id exists in the provided batch.
- If nothing is suspicious, return an empty suspicious array.
- Evaluate risk using only these signals when present: amount, channel, location, device, merchant type, and unusual behavior across the batch.
- Prefer concise, evidence-based reasons.
- Return valid JSON only. Do not wrap the JSON in markdown fences.

Return this exact JSON shape:
{{
  "batch_id": "{batch_id}",
  "suspicious": [
    {{
      "id": "txn_0007",
      "risk_score": 0.95,
      "reasons": ["high amount", "unknown device", "foreign location"]
    }}
  ]
}}

Additional constraints:
- risk_score must be between 0 and 1.
- reasons must be a list of short strings.
- Keep the batch_id exactly as "{batch_id}".

Transactions:
{transaction_json}
""".strip()


def validate_ids_exist(transactions: list[dict[str, Any]], suspicious_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter model output so only transaction IDs from the input batch survive."""

    valid_ids = {str(transaction.get("id")) for transaction in transactions if transaction.get("id")}
    validated: list[dict[str, Any]] = []

    for item in suspicious_items:
        candidate_id = str(item.get("id", "")).strip()
        if candidate_id not in valid_ids:
            continue

        raw_score = item.get("risk_score", 0)
        try:
            risk_score = float(raw_score)
        except (TypeError, ValueError):
            risk_score = 0.0

        normalized_reasons = [
            str(reason).strip()
            for reason in item.get("reasons", [])
            if isinstance(reason, str) and reason.strip()
        ]

        validated.append(
            {
                "id": candidate_id,
                "risk_score": max(0.0, min(1.0, risk_score)),
                "reasons": normalized_reasons,
            }
        )

    return validated


def parse_model_response(content: str, batch_id: str, transactions: list[dict[str, Any]]) -> dict[str, Any]:
    """Parse and normalize the model JSON response into the expected output shape."""

    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return empty_result(batch_id)

    if not isinstance(payload, dict):
        return empty_result(batch_id)

    suspicious_items = payload.get("suspicious", [])
    if not isinstance(suspicious_items, list):
        suspicious_items = []

    validated_items = validate_ids_exist(transactions, suspicious_items)
    returned_batch_id = payload.get("batch_id")

    return {
        "batch_id": returned_batch_id if returned_batch_id == batch_id else batch_id,
        "suspicious": validated_items,
    }


def build_client() -> Any:
    """Create an async OpenAI client using the configured API key."""

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    openai_module = importlib.import_module("openai")
    async_openai = getattr(openai_module, "AsyncOpenAI")
    return async_openai(api_key=api_key)


async def analyze_batch(batch_id: str, transactions: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze one batch of transactions and return validated suspicious results.

    The function always returns a safe dictionary in the expected shape, even if the
    OpenAI request fails or the model returns invalid JSON.
    """

    if not transactions:
        return empty_result(batch_id)

    prompt = build_prompt(batch_id, transactions)

    try:
        client = build_client()
        response = await client.chat.completions.create(
            model=DEFAULT_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You detect suspicious financial transactions and output strict JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
        )
    except Exception:
        return empty_result(batch_id)

    message = response.choices[0].message if response.choices else None
    content = message.content if message and message.content else ""

    if not isinstance(content, str) or not content.strip():
        return empty_result(batch_id)

    return parse_model_response(content, batch_id, transactions)
