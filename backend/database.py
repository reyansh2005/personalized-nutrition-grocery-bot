"""SQLite persistence for grocery prices and the user's pantry."""

from __future__ import annotations

import sqlite3
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "grocery.db"
USDA_DATASET_PATH = Path(
    os.getenv("USDA_DATASET_PATH", str(PROJECT_ROOT / "data" / "usda_foundation_foods.json"))
)

PRICE_SEED_DATA = [
    ("Chicken Breast", 5.99, "lb", False),
    ("Brown Rice", 2.49, "lb", False),
    ("Canned Beans", 1.29, "can", False),
    ("Eggs", 3.49, "dozen", False),
    ("Greek Yogurt", 4.99, "32 oz", True),
    ("Butter", 4.49, "lb", True),
    ("Olive Oil", 8.99, "500 ml", False),
    ("Almond Milk", 3.99, "half gallon", False),
    ("Spinach", 2.99, "bag", False),
    ("Bananas", 0.69, "lb", False),
]


def get_connection() -> sqlite3.Connection:
    """Create a connection with dictionary-like rows and safe foreign keys."""
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    """Create tables and seed prices once."""
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS prices (
                item_name TEXT PRIMARY KEY,
                price_per_unit REAL NOT NULL CHECK (price_per_unit >= 0),
                unit TEXT NOT NULL,
                is_dairy INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS pantry (
                item_name TEXT PRIMARY KEY,
                quantity REAL NOT NULL CHECK (quantity >= 0),
                unit TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS food_products (
                barcode TEXT PRIMARY KEY,
                product_name TEXT NOT NULL,
                brands TEXT NOT NULL DEFAULT '',
                ingredients_text TEXT NOT NULL DEFAULT '',
                allergens TEXT NOT NULL DEFAULT '',
                allergens_tags TEXT NOT NULL DEFAULT '[]',
                categories TEXT NOT NULL DEFAULT '',
                energy_kcal_100g REAL,
                protein_g_100g REAL,
                fat_g_100g REAL,
                carbohydrates_g_100g REAL,
                fiber_g_100g REAL,
                source TEXT NOT NULL,
                source_url TEXT NOT NULL,
                cached_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS nutrition (
                fdc_id INTEGER PRIMARY KEY,
                food_name TEXT NOT NULL,
                calories REAL,
                protein_g REAL,
                fat_g REAL,
                carbohydrates_g REAL,
                fiber_g REAL,
                sodium_mg REAL,
                calcium_mg REAL,
                serving_size REAL,
                serving_unit TEXT,
                source TEXT NOT NULL,
                source_url TEXT,
                imported_at TEXT NOT NULL
            );
            """
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO prices
                (item_name, price_per_unit, unit, is_dairy)
            VALUES (?, ?, ?, ?)
            """,
            PRICE_SEED_DATA,
        )
    import_usda_foundation_foods()


def _nutrient_amount(food: dict[str, Any], names: tuple[str, ...]) -> float | None:
    for food_nutrient in food.get("foodNutrients", []):
        nutrient = food_nutrient.get("nutrient") or {}
        if nutrient.get("name") in names and food_nutrient.get("amount") is not None:
            return float(food_nutrient["amount"])
    return None


def import_usda_foundation_foods() -> int:
    """Import the USDA Foundation Foods export into the local nutrition table."""
    if not USDA_DATASET_PATH.exists():
        return 0
    with USDA_DATASET_PATH.open(encoding="utf-8") as dataset_file:
        foods = json.load(dataset_file).get("FoundationFoods", [])
    imported_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for food in foods:
        portions = food.get("foodPortions") or []
        portion = portions[0] if portions else {}
        rows.append(
            (
                food.get("fdcId"),
                food.get("description", "Unnamed food"),
                _nutrient_amount(
                    food,
                    (
                        "Energy",
                        "Energy (Atwater General Factors)",
                        "Energy (Atwater Specific Factors)",
                    ),
                ),
                _nutrient_amount(food, ("Protein",)),
                _nutrient_amount(food, ("Total lipid (fat)",)),
                _nutrient_amount(
                    food,
                    ("Carbohydrate, by difference", "Carbohydrate, by summation"),
                ),
                _nutrient_amount(food, ("Fiber, total dietary",)),
                _nutrient_amount(food, ("Sodium, Na",)),
                _nutrient_amount(food, ("Calcium, Ca",)),
                portion.get("amount"),
                portion.get("measureUnit", {}).get("name"),
                "USDA FoodData Central Foundation Foods",
                f"https://fdc.nal.usda.gov/fdc-app.html#/food-details/{food.get('fdcId')}/nutrients",
                imported_at,
            )
        )
    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO nutrition (
                fdc_id, food_name, calories, protein_g, fat_g, carbohydrates_g,
                fiber_g, sodium_mg, calcium_mg, serving_size, serving_unit,
                source, source_url, imported_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fdc_id) DO UPDATE SET
                food_name = excluded.food_name,
                calories = excluded.calories,
                protein_g = excluded.protein_g,
                fat_g = excluded.fat_g,
                carbohydrates_g = excluded.carbohydrates_g,
                fiber_g = excluded.fiber_g,
                sodium_mg = excluded.sodium_mg,
                calcium_mg = excluded.calcium_mg,
                serving_size = excluded.serving_size,
                serving_unit = excluded.serving_unit,
                source = excluded.source,
                source_url = excluded.source_url,
                imported_at = excluded.imported_at
            """,
            rows,
        )
    return len(rows)


def search_nutrition(keywords: list[str], limit: int = 8) -> list[dict[str, Any]]:
    """Search imported USDA foods by description."""
    if not keywords:
        return []
    clauses = ["LOWER(food_name) LIKE ?" for _ in keywords[:8]]
    parameters = [f"%{keyword.lower()}%" for keyword in keywords[:8]]
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT fdc_id, food_name, calories, protein_g, fat_g, carbohydrates_g, "
            "fiber_g, sodium_mg, calcium_mg, serving_size, serving_unit, source, source_url "
            f"FROM nutrition WHERE {' OR '.join(clauses)} "
            "ORDER BY CASE WHEN protein_g IS NULL THEN 1 ELSE 0 END, protein_g DESC LIMIT ?",
            [*parameters, limit],
        ).fetchall()
    return [dict(row) for row in rows]


def cache_food_product(product: dict[str, Any]) -> None:
    """Persist a normalized external product so chat requests can work offline."""
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO food_products (
                barcode, product_name, brands, ingredients_text, allergens,
                allergens_tags, categories, energy_kcal_100g, protein_g_100g,
                fat_g_100g, carbohydrates_g_100g, fiber_g_100g, source, source_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(barcode) DO UPDATE SET
                product_name = excluded.product_name,
                brands = excluded.brands,
                ingredients_text = excluded.ingredients_text,
                allergens = excluded.allergens,
                allergens_tags = excluded.allergens_tags,
                categories = excluded.categories,
                energy_kcal_100g = excluded.energy_kcal_100g,
                protein_g_100g = excluded.protein_g_100g,
                fat_g_100g = excluded.fat_g_100g,
                carbohydrates_g_100g = excluded.carbohydrates_g_100g,
                fiber_g_100g = excluded.fiber_g_100g,
                source = excluded.source,
                source_url = excluded.source_url,
                cached_at = CURRENT_TIMESTAMP
            """,
            (
                product["barcode"],
                product["product_name"],
                product["brands"],
                product["ingredients_text"],
                product["allergens"],
                json.dumps(product["allergens_tags"]),
                product["categories"],
                product["energy_kcal_100g"],
                product["protein_g_100g"],
                product["fat_g_100g"],
                product["carbohydrates_g_100g"],
                product["fiber_g_100g"],
                product["source"],
                product["source_url"],
            ),
        )


def get_cached_food_product(barcode: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM food_products WHERE barcode = ?", (barcode,)
        ).fetchone()
    if row is None:
        return None
    product = dict(row)
    product["allergens_tags"] = json.loads(product["allergens_tags"])
    return product


def add_pantry_item(item_name: str, quantity: float, unit: str) -> dict[str, Any]:
    """Insert or increment a pantry item."""
    normalized_name = item_name.strip()
    normalized_unit = unit.strip()
    if not normalized_name or not normalized_unit or quantity < 0:
        raise ValueError("item_name and unit are required; quantity must be non-negative")
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO pantry (item_name, quantity, unit) VALUES (?, ?, ?)
            ON CONFLICT(item_name) DO UPDATE SET
                quantity = quantity + excluded.quantity,
                unit = excluded.unit
            """,
            (normalized_name, quantity, normalized_unit),
        )
        row = connection.execute(
            "SELECT item_name, quantity, unit FROM pantry WHERE item_name = ?",
            (normalized_name,),
        ).fetchone()
    return dict(row)


def list_pantry() -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT item_name, quantity, unit FROM pantry ORDER BY item_name"
        ).fetchall()
    return [dict(row) for row in rows]


def remove_pantry_item(item_name: str) -> bool:
    """Remove a pantry item by its normalized name."""
    normalized_name = item_name.strip()
    if not normalized_name:
        raise ValueError("item_name is required")
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM pantry WHERE item_name = ?", (normalized_name,)
        )
    return cursor.rowcount > 0


def search_prices(
    keywords: list[str] | None = None,
    max_price: float | None = None,
    dairy_only: bool | None = None,
) -> list[dict[str, Any]]:
    """Find matching grocery prices, optionally constrained by a budget."""
    clauses: list[str] = []
    parameters: list[Any] = []
    if keywords:
        keyword_clauses = []
        for keyword in keywords:
            keyword_clauses.append("LOWER(item_name) LIKE ?")
            parameters.append(f"%{keyword.lower()}%")
        clauses.append("(" + " OR ".join(keyword_clauses) + ")")
    if max_price is not None:
        clauses.append("price_per_unit <= ?")
        parameters.append(max_price)
    if dairy_only is not None:
        clauses.append("is_dairy = ?")
        parameters.append(int(dairy_only))
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT item_name, price_per_unit, unit, is_dairy FROM prices"
            + where
            + " ORDER BY price_per_unit, item_name",
            parameters,
        ).fetchall()
    return [dict(row) for row in rows]


def lookup_items(
    keywords: list[str],
    max_price: float | None = None,
    dairy_only: bool | None = None,
) -> dict[str, Any]:
    """Return both price matches and pantry contents for agent prompting."""
    return {
        "prices": search_prices(keywords, max_price, dairy_only),
        "pantry": list_pantry(),
        "nutrition": search_nutrition(keywords),
    }


init_db()
