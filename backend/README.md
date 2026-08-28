# Astra AI Explore API

## Run locally

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`, with interactive docs at `/docs`.

## Product endpoints

- `GET /api/v1/explore/products` fetches the complete catalog from the database.
- `GET /api/v1/explore/products/{product_id}` fetches one product from the database.
- `POST /api/v1/explore/search` searches and filters database products.

## Search request

`POST /api/v1/explore/search` uses `multipart/form-data`. Text searches send `text_query`; voice searches send an audio `audio_file`; image searches send an `image_file`. Filters include `category`, `min_price`, `max_price`, repeated `semantic_tags`, `sort_by`, `page`, and `limit`.

Products use PostgreSQL when `ASTRA_DATABASE_URL` (or `DATABASE_URL`) is set, and otherwise use local SQLite at `.astra_ai.db`. Install dependencies, set the URL, then start the API:

```powershell
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Create `backend/.env` from `.env.example` and add your PostgreSQL URL before starting the API. Never commit `backend/.env`.

The catalog is seeded on first use. The repository boundary in `app/repository.py` keeps the API and search service independent of the database engine. The voice and image functions remain local deterministic placeholders until Whisper and a vision encoder are connected.

## Test

```powershell
python -m pytest -q
```
