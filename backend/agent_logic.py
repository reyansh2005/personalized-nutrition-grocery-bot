"""Agent orchestration: budget/pantry lookup, RAG, and OpenAI-compatible LLM."""

from __future__ import annotations

import os
import re
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from .database import lookup_items
from .open_food_facts import get_product_by_barcode
from .rag_pipeline import retrieve_context

load_dotenv()


def _extract_budget(query: str) -> float | None:
    match = re.search(r"\$(\d+(?:\.\d{1,2})?)|(?:budget|under|spend)\s*(?:is|of|:)?\s*(\d+(?:\.\d{1,2})?)", query, re.I)
    if not match:
        return None
    return float(next(value for value in match.groups() if value is not None))


def _extract_keywords(query: str) -> list[str]:
    common = {
        "i", "me", "my", "a", "an", "the", "and", "or", "with", "for", "under",
        "have", "want", "need", "make", "meal", "plan", "budget", "is", "dairy",
        "allergy", "allergic", "to", "no", "please", "give", "options",
    }
    return [word for word in re.findall(r"[a-zA-Z]{3,}", query.lower()) if word not in common]


def _dairy_preference(query: str) -> bool | None:
    """Return True for dairy requests, False for dairy avoidance, or None if unspecified."""
    normalized = query.lower()
    dairy_free = (
        "dairy-free" in normalized
        or "dairy free" in normalized
        or "no dairy" in normalized
        or "lactose intoler" in normalized
        or "allergic to dairy" in normalized
    )
    if dairy_free:
        return False
    if re.search(r"\b(dairy|milk|yogurt|cheese|butter)\b", normalized):
        return True
    return None


def _fallback_answer(user_query: str, db_data: dict[str, Any], context: str) -> str:
    """Keep local development useful when no LLM credentials are configured."""
    budget = _extract_budget(user_query) or 20.0
    prices = db_data["prices"]
    selected = prices[:]
    total = 0.0
    chosen = []
    for item in selected:
        if total + item["price_per_unit"] <= budget:
            chosen.append(item)
            total += item["price_per_unit"]
    names = ", ".join(item["item_name"] for item in chosen[:4]) or "beans and rice"
    dairy_preference = _dairy_preference(user_query)
    substitution = (
        "Dairy-free substitutions: use olive oil instead of butter and almond milk instead of dairy milk."
        if dairy_preference is False
        else "Dairy options can include Greek yogurt, butter, or dairy milk when they fit the request."
    )
    return (
        f"Mock high-protein plan within ${budget:.2f}: use {names}. "
        f"{substitution} "
        f"Estimated grocery total: ${total:.2f}.\n\nRelevant nutrition context:\n{context[:800]}"
    )


def process_query(user_query: str) -> dict[str, Any]:
    """Process a user request and return answer metadata for the API."""
    budget = _extract_budget(user_query)
    dairy_preference = _dairy_preference(user_query)
    db_data = lookup_items(_extract_keywords(user_query), budget, dairy_preference)
    barcode_match = re.search(r"\b\d{8,14}\b", user_query)
    external_product = (
        get_product_by_barcode(barcode_match.group()) if barcode_match else None
    )
    context = retrieve_context(user_query)
    system_prompt = (
        "You are a strict nutrition bot. Honor every allergy constraint, especially no dairy. "
        "Explicitly name a non-dairy substitute whenever dairy appears. Create a mock high-protein "
        "meal plan that fits the user's budget. Use only the supplied database and context for "
        "prices and context for nutrition; clearly label estimates. If the user asks for dairy "
        "options, include suitable dairy items rather than silently filtering them out. If the "
        "user asks for dairy-free food, do not recommend any item marked is_dairy=true."
    )
    api_key = os.getenv("LLM_API_KEY")
    if not api_key or api_key.lower() in {"your-key", "change-me", "none"}:
        answer = _fallback_answer(user_query, db_data, context)
    else:
        client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("LLM_API_BASE", "https://api.groq.com/openai/v1"),
        )
        response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL_ID", "openai/gpt-oss-20b"),
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Question: {user_query}\nBudget: {budget or 'not specified'}\n"
                        f"Database JSON: {db_data}\nExternal product: {external_product}\n"
                        f"Retrieved context:\n{context}"
                    ),
                },
            ],
        )
        answer = response.choices[0].message.content or "The model returned an empty answer."
    return {
        "answer": answer,
        "pantry": db_data["pantry"],
        "budget_used": budget or 0.0,
        "external_product": external_product,
    }
