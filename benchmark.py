"""Measure the nutrition bot's data and generation path for the ESE report."""

from __future__ import annotations

import json
import os
import time
from typing import Any

from dotenv import load_dotenv

from backend.database import lookup_items
from backend.rag_pipeline import retrieve_context

load_dotenv()

TEST_PROMPT = (
    "I want a high-protein dinner tonight that fits my $20 grocery budget. "
    "Also, I'm allergic to dairy. Check what I already have in my pantry."
)


def _mock_llm_output(pantry: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a deterministic offline response when no provider key is configured."""
    return {
        "answer": (
            "Chicken & Bean Rice Bowl: a high-protein, dairy-free dinner "
            "that fits the $20 grocery budget."
        ),
        "meal": "Chicken & Bean Rice Bowl",
        "dietary_constraint": "Dairy-free",
        "budget": 20.0,
        "ingredients": [
            {
                "name": "Chicken Breast",
                "quantity": "200g",
                "protein_g": 62.0,
                "price": 3.00,
                "is_in_pantry": False,
            },
            {
                "name": "Brown Rice",
                "quantity": "150g",
                "protein_g": 4.05,
                "price": 0.50,
                "is_in_pantry": True,
            },
            {
                "name": "Canned Beans",
                "quantity": "100g",
                "protein_g": 8.7,
                "price": 0.75,
                "is_in_pantry": True,
            },
        ],
        "total_protein_g": 74.8,
        "total_estimated_cost": 5.35,
        "actual_out_of_pocket_cost": 1.85,
        "pantry": pantry,
    }


def _llm_call(context: str, pantry: list[dict[str, Any]]) -> dict[str, Any]:
    api_key = os.getenv("LLM_API_KEY", "")
    if not api_key or api_key.lower() in {"your-key", "change-me", "none"}:
        return _mock_llm_output(pantry)

    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("LLM_API_BASE", "https://api.groq.com/openai/v1"),
    )
    response = client.chat.completions.create(
        model=os.getenv("LLM_MODEL_ID", "openai/gpt-oss-20b"),
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": (
                    "Return JSON with answer, meal, dietary_constraint, budget, "
                    "ingredients, total_protein_g, total_estimated_cost, and "
                    "actual_out_of_pocket_cost. Do not recommend dairy."
                ),
            },
            {
                "role": "user",
                "content": f"{TEST_PROMPT}\nPantry: {pantry}\nContext: {context}",
            },
        ],
    )
    content = (response.choices[0].message.content or "").strip()
    return {"answer": content, "pantry": pantry}


def main() -> None:
    total_start = time.perf_counter()

    sql_start = time.perf_counter()
    data = lookup_items(
        ["chicken", "brown", "rice", "beans", "dairy"],
        max_price=20.0,
        dairy_only=False,
    )
    sql_ms = (time.perf_counter() - sql_start) * 1000

    retrieval_start = time.perf_counter()
    context = retrieve_context(TEST_PROMPT)
    retrieval_ms = (time.perf_counter() - retrieval_start) * 1000

    llm_start = time.perf_counter()
    llm_output = _llm_call(context, data["pantry"])
    llm_ms = (time.perf_counter() - llm_start) * 1000

    total_ms = (time.perf_counter() - total_start) * 1000
    mode = "provider" if os.getenv("LLM_API_KEY", "").lower() not in {
        "",
        "your-key",
        "change-me",
        "none",
    } else "mock_no_api_key"

    print(f"SQL_Query_ms: {sql_ms:.3f}")
    print(f"ChromaDB_Retrieval_ms: {retrieval_ms:.3f}")
    print(f"LLM_Inference_ms: {llm_ms:.3f}")
    print(f"LLM_Mode: {mode}")
    print(f"Total_E2E_ms: {total_ms:.3f}")
    print("Test_Prompt:")
    print(TEST_PROMPT)
    print("Exact_JSON_Output:")
    print(json.dumps(llm_output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
