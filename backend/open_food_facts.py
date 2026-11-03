"""Open Food Facts integration with a local SQLite cache."""

from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv

from .database import cache_food_product, get_cached_food_product

load_dotenv()

OPEN_FOOD_FACTS_API_BASE = os.getenv(
    "OPEN_FOOD_FACTS_API_BASE", "https://world.openfoodfacts.org/api/v3"
)
USER_AGENT = os.getenv(
    "OPEN_FOOD_FACTS_USER_AGENT",
    "PersonalizedNutritionBot/1.0 (local development)",
)


class ExternalFoodDataError(RuntimeError):
    """Raised when Open Food Facts cannot provide a usable response."""


class FoodProductNotFound(ExternalFoodDataError):
    """Raised when a barcode is valid but absent from Open Food Facts."""


def _normalize_product(barcode: str, product: dict[str, Any]) -> dict[str, Any]:
    nutriments = product.get("nutriments") or {}
    return {
        "barcode": barcode,
        "product_name": product.get("product_name") or "Unnamed product",
        "brands": product.get("brands") or "",
        "ingredients_text": product.get("ingredients_text") or "",
        "allergens": product.get("allergens") or "",
        "allergens_tags": product.get("allergens_tags") or [],
        "categories": product.get("categories") or "",
        "energy_kcal_100g": nutriments.get("energy-kcal_100g"),
        "protein_g_100g": nutriments.get("proteins_100g"),
        "fat_g_100g": nutriments.get("fat_100g"),
        "carbohydrates_g_100g": nutriments.get("carbohydrates_100g"),
        "fiber_g_100g": nutriments.get("fiber_100g"),
        "source": "Open Food Facts",
        "source_url": f"https://world.openfoodfacts.org/product/{barcode}",
    }


def get_product_by_barcode(barcode: str, refresh: bool = False) -> dict[str, Any]:
    """Fetch a product from Open Food Facts, using SQLite as a cache."""
    normalized_barcode = barcode.strip()
    if not normalized_barcode.isdigit() or not 8 <= len(normalized_barcode) <= 14:
        raise ValueError("barcode must contain 8 to 14 digits")
    if not refresh:
        cached = get_cached_food_product(normalized_barcode)
        if cached:
            cached["from_cache"] = True
            return cached

    url = f"{OPEN_FOOD_FACTS_API_BASE.rstrip('/')}/product/{normalized_barcode}.json"
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
        if response.status_code == 404:
            raise FoodProductNotFound(
                f"No Open Food Facts product was found for barcode {normalized_barcode}."
            )
        response.raise_for_status()
        payload = response.json()
    except FoodProductNotFound:
        raise
    except (requests.RequestException, ValueError) as exc:
        raise ExternalFoodDataError(
            "Open Food Facts is unavailable; try again or use a cached barcode."
        ) from exc
    successful_status = payload.get("status") in (1, "1", "success")
    if not successful_status or not isinstance(payload.get("product"), dict):
        raise FoodProductNotFound(
            f"No Open Food Facts product was found for barcode {normalized_barcode}."
        )

    product = _normalize_product(normalized_barcode, payload["product"])
    cache_food_product(product)
    product["from_cache"] = False
    return product
