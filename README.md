# WP TLDR Explorer

Ingests Western Producer articles via the [WordPress REST API](https://www.producer.com/wp-json/wp/v2) (no scraping required), classifies them by topic, summarizes via LLM, and serves a vanilla HTML/JS explorer UI.

**Topics:** AgTech (primary lens), Livestock, Crops, Markets, Politics — with date-range filtering, full-text search, and on-demand drill-down expansion.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and add your `LLM_API_KEY` (DeepSeek, Gemini, etc.). Leave it **blank** to use the bundled local model instead — no key or internet needed at runtime.

## Local model (no API key required)

When `LLM_API_KEY` is blank, the app runs a small Qwen2.5-0.5B-Instruct model on your CPU (via `llama-cpp-python`):

- The ~470 MB GGUF file is **downloaded automatically on first use** into `models/` (gitignored) and cached from then on — the app works fully offline afterwards.
- If a `LLM_API_KEY` *is* set, the app uses that cloud provider (DeepSeek/Gemini/OpenAI-compatible) instead and ignores the local model.
- Related settings in `.env` / `.env.example`: `LOCAL_MODEL_PATH`, `LOCAL_MODEL_URL`, `LOCAL_MODEL_N_THREADS`, `SUMMARIZE_LIMIT`.
- To pre-fetch the model without using the app: `python -m backend.update --topic agtech`.

### LLM routing test

```bash
python -m backend.llm --check
```

Prints whether the cloud API or the local model is in use.

## Quick Start

```bash
# 1. Start the API server
uvicorn backend.main:app --reload

# 2. Open http://127.0.0.1:8000 in a browser
```

## Pipeline Commands

Run from the project root:

```bash
# Ingest articles from date range
python -m backend.ingest --start 2026-01-01 --end 2026-07-24

# Classify articles into topics (deterministic, no LLM needed)
python -m backend.classify

# Summarize articles by topic
python -m backend.summarize --topic agtech --limit 50

# Summarize other topics as needed
python -m backend.summarize --topic livestock --limit 50
python -m backend.summarize --topic crops --limit 50

# Update pipeline: fetch new articles since last ingest, classify, summarize (all topics)
python -m backend.update

# Summarize a single topic only (what the UI's Update button does)
python -m backend.update --topic agtech
```

## Topic Brief (LLM one-pager per topic + date range)

```bash
# Generate a digest for crops in July 2026
python -m backend.digest --topic crops --from 2026-07-01 --to 2026-07-31

# Dry run (prints JSON, no DB write)
python -m backend.digest --topic agtech --from 2026-07-01 --to 2026-07-31 --dry-run

# Force regeneration (bypasses cache)
python -m backend.digest --topic markets --from 2026-01-01 --to 2026-06-30 --force
```

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/health` | Health check |
| `GET /api/stats` | Article/summary counts |
| `GET /api/topics?from=&to=` | Topic counts |
| `GET /api/articles?topic=&from=&to=&q=&page=` | Paginated article list |
| `GET /api/articles/{id}` | Full article + summary + related |
| `POST /api/articles/{id}/expand` | LLM drill-down (cached) |
| `POST /api/update?topic=agtech` | Trigger data update pipeline for one topic (background) |
| `GET /api/update/status` | Update pipeline progress |
| `POST /api/digest?topic=&from=&to=&force=` | Generate topic brief (cached) |
| `GET /api/digest?topic=&from=&to=` | Retrieve cached topic brief |

## UI Features

- **Topic pills** — filter by AgTech, Livestock, Crops, Markets, Politics
- **Date range + search** — scope articles by date and keyword
- **Drill-down** — click an article card to see full summary, key points, related articles; "Go Deeper" for LLM expansion
- **Update data** — fetch new articles from the Western Producer, re-run classification, and summarize the **currently selected topic** (one topic per run, using the local model or cloud API).
- **Topic Brief** — generate a one-page LLM-written brief for the active topic and date range, with themes, key stories (clickable), context, and outlook

## Project Layout

```
backend/     FastAPI app + pipeline scripts
frontend/    Static HTML/CSS/JS
tests/       pytest suite
data/        SQLite database (gitignored)
```
