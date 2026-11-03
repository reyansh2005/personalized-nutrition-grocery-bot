"""FastAPI application for the personalized nutrition and grocery bot."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .agent_logic import process_query
from .database import (
    add_pantry_item,
    init_db,
    list_pantry,
    remove_pantry_item,
    search_nutrition,
)
from .open_food_facts import (
    ExternalFoodDataError,
    FoodProductNotFound,
    get_product_by_barcode,
)

app = FastAPI(title="Personalized Nutrition & Grocery Bot", version="1.0.0")


class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)


class PantryItemRequest(BaseModel):
    item_name: str = Field(..., min_length=1, max_length=100)
    quantity: float = Field(..., ge=0)
    unit: str = Field(..., min_length=1, max_length=30)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ask")
def ask(request: QuestionRequest) -> dict:
    try:
        return process_query(request.question)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Unable to process nutrition request: {exc}") from exc


@app.post("/pantry")
def add_pantry(request: PantryItemRequest) -> dict:
    try:
        return add_pantry_item(request.item_name, request.quantity, request.unit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/pantry")
def get_pantry() -> list[dict]:
    return list_pantry()


@app.get("/nutrition/search")
def nutrition_search(query: str, limit: int = 8) -> list[dict]:
    if not query.strip():
        raise HTTPException(status_code=422, detail="query is required")
    if not 1 <= limit <= 50:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 50")
    keywords = [word for word in query.split() if len(word) >= 3]
    return search_nutrition(keywords, limit)


@app.delete("/pantry/{item_name}")
def delete_pantry(item_name: str) -> dict[str, str]:
    try:
        removed = remove_pantry_item(item_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not removed:
        raise HTTPException(status_code=404, detail="Pantry item not found")
    return {"status": "removed"}


@app.get("/foods/barcode/{barcode}")
@app.get("/food/barcode/{barcode}", include_in_schema=False)
def get_food_by_barcode(barcode: str, refresh: bool = False) -> dict:
    """Return live or cached nutrition and allergen data from Open Food Facts."""
    try:
        return get_product_by_barcode(barcode, refresh=refresh)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FoodProductNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExternalFoodDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
