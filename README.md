# WP TLDR Explorer

Ingests Western Producer articles via the [WordPress REST API](https://www.producer.com/wp-json/wp/v2) (no scraping required), classifies them by topic, summarizes via LLM, and serves a vanilla HTML/JS explorer UI.

**Topics:** AgTech (primary lens), Livestock, Crops, Markets, Politics, Unclassified — with date-range filtering, full-text search, and on-demand drill-down expansion. Articles that don't match any topic are grouped under **Unclassified**.

## Download & Install (no coding required)

The app ships as a pre-built desktop app. You do **not** need Python, Node, or any developer tools. Steps below take you from the GitHub page to a running app.

### Windows (PC)

1. Go to https://github.com/BHBD1986/wptldr
2. On the right side of the page, click **Releases** (under "About"). If a box showing "Latest release" appears, click it instead.
3. Find the latest release. Under **Assets**, click **`WPTLDR-Setup-vX.X.X.exe`** to download it.
   - No `.exe` in the list? Download **`WPTLDR-windows-x64-vX.X.X.zip`** instead and skip to step 8.
4. Double-click the downloaded `WPTLDR-Setup-vX.X.X.exe` file.
5. Windows SmartScreen may show a blue "Windows protected your PC" warning. Click **More info**, then **Run anyway**. (This is a one-time step — the app isn't code-signed yet.)
6. Follow the installer wizard: accept the default folder and click **Next** → **Install**. It adds a **Start-menu entry** and a **Desktop shortcut**.
7. Launch the app by double-clicking the **WP TLDR** desktop shortcut (or the Start-menu entry).
8. **First launch:** a small status window opens and the app downloads the ~470 MB AI model automatically (takes a few minutes the first time). Wait for the status text to say the server is ready — your browser opens on its own.

**Zip fallback (if you used the `.zip` in step 3):** right-click the zip → **Extract All**, open the extracted `WPTLDR` folder, and double-click **`WPTLDR.exe`**. First launch downloads the model as in step 8.

### Mac

1. Go to https://github.com/BHBD1986/wptldr
2. On the right side of the page, click **Releases** (under "About"). If a box showing "Latest release" appears, click it instead.
3. Find the latest release. Under **Assets**, click **`WPTLDR-macos-arm64-vX.X.X.zip`** to download it. (This build is for Apple Silicon M-series Macs.)
4. Double-click the downloaded `.zip` to unzip it — a **`WPTLDR.app`** icon appears.
5. Drag **`WPTLDR.app`** into your **Applications** folder.
6. **First open:** right-click (or Ctrl-click) **`WPTLDR.app`** in Applications → **Open** → click **Open** in the dialog. (This is the one-time Gatekeeper bypass — the app isn't notarized yet. After this, normal double-click works.)
7. Launch the app by double-clicking **WP TLDR** in Applications.
8. **First launch:** a small status window opens and the app downloads the ~470 MB AI model automatically (takes a few minutes the first time). Wait for the status text to say the server is ready — your browser opens on its own.

### After install (both platforms)

- A browser tab opens at the app's local address (e.g. `http://127.0.0.1:PORT`) — that's the app UI.
- The small status window stays open while the app runs; use its **Quit** button to close the app (or quit from the taskbar/status menu).
- Updating: when a new release is posted, download the new installer and run it — your saved data is kept.

---

## Developer Setup

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
