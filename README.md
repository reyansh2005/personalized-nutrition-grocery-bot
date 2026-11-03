# Personalized Nutrition & Grocery Bot

A full-stack demo that combines a FastAPI service, Streamlit chat UI, SQLite grocery/pantry data, LangChain + Chroma retrieval, and an OpenAI-compatible LLM.

The application integrates [Open Food Facts](https://world.openfoodfacts.org/) as an external food database and USDA FoodData Central Foundation Foods as a local nutrition database. Barcode lookups fetch product nutrition, ingredients, and allergens from the live API, while the USDA export provides structured nutrient values for meal planning.

## Setup

From the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `LLM_API_KEY` in `.env` for Groq or another OpenAI-compatible provider. The default model is Groq's open-weight `openai/gpt-oss-20b`. Without a key, the API uses a deterministic local mock response so the database and UI can still be tested. The first RAG request downloads `all-MiniLM-L6-v2`, so allow network access and disk space.

The project includes `data/usda_foundation_foods.json`, a USDA FoodData Central Foundation Foods export. On startup it is imported into the SQLite `nutrition` table. Set `USDA_DATASET_PATH` in `.env` to use a different export.

For small cloud instances, set `ENABLE_RAG=false` to skip the memory-intensive first-time embedding and ChromaDB initialization. The application will continue using SQLite, USDA nutrition data, pantry data, and the configured LLM. Keep `ENABLE_RAG=true` for local development or a larger instance.

## Run the backend

```powershell
uvicorn backend.main:app --reload
```

The API is available at `http://localhost:8000`. OpenAPI documentation is at `/docs`.

### USDA nutrition search

Search the imported USDA records:

```powershell
Invoke-RestMethod "http://localhost:8000/nutrition/search?query=chicken&limit=3"
```

The response includes calories, protein, fat, carbohydrates, fiber, sodium, calcium, serving information, and a USDA source URL. Meal-planning requests also receive matching USDA nutrition records automatically.

### Open Food Facts lookup

Test the external food database directly:

```powershell
Invoke-RestMethod http://localhost:8000/foods/barcode/3017620422003
```

The example barcode is Nutella. The response includes product name, ingredients, allergens, nutrition per 100 g, source URL, and whether the result came from the local cache. Add a barcode to a chat question and the product will also be included in the LLM prompt:

```text
Is product 3017620422003 safe for someone allergic to dairy?
```

The API identifies itself with `OPEN_FOOD_FACTS_USER_AGENT`, which is required for responsible API use. Results are cached in the `food_products` SQLite table. Use `?refresh=true` to bypass the cache.

If you see `404 Not Found` from FastAPI, restart the backend after pulling the latest code:

```powershell
uvicorn backend.main:app --reload
```

Then verify `http://localhost:8000/health` returns `{"status":"ok"}`. A valid but unknown barcode returns a product-specific 404; use a real barcode or the tested example above.

## Run the frontend

In another terminal:

```powershell
streamlit run frontend/streamlit_app.py
```

The sidebar shows pantry contents and the active budget. Example pantry request:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/pantry `
  -ContentType "application/json" `
  -Body '{"item_name":"Brown Rice","quantity":2,"unit":"lb"}'
```

## RAG knowledge base

`data/recipes.txt` and `data/usda_nutrition.pdf` are loaded, split into 500-character chunks with 50-character overlap, embedded with `all-MiniLM-L6-v2`, and persisted in `.chroma/`. The pipeline stores a source signature and automatically rebuilds the Chroma collection when either source document changes.
