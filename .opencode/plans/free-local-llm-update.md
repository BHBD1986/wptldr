# Plan: Free local LLM for Update Data button

**Goal:** Make the "Update data" button work without a paid API key, stably for 12+ months, by bundling a small local model. Summarize only the active topic per update run.

## Overview

Today the update pipeline (`backend/update.py`) runs ingestion (free) → classification (free, deterministic) → **summarization for all 5 topics**, which calls `backend/llm.py:chat()` and requires a paid `LLM_API_KEY` (DeepSeek). We will:
- Add a **local inference backend** using `llama-cpp-python` + a bundled **Qwen2.5-0.5B-Instruct** GGUF model (~400 MB) that runs on CPU.
- Make `chat()` **local-first, cloud-fallback**: if `LLM_API_KEY` is set it uses the existing OpenAI-compatible path (DeepSeek/Gemini/Groq); otherwise it uses the local model.
- Reduce the update button to **one topic at a time** (the currently selected pill), so a small model is never overwhelmed.
- Use JSON grammar–constrained decoding so the 0.5B model emits valid JSON reliably for summaries/digests/expand.

## Tasks

- [x] **Config & deps** — Add `LOCAL_MODEL_PATH`, `LOCAL_MODEL_URL`, `LOCAL_MODEL_N_THREADS`, `SUMMARIZE_LIMIT` to `backend/config.py`; add `llama-cpp-python` to `requirements.txt`; update `.env.example`.
- [x] **Local inference module** (`backend/local_llm.py`) — Lazy-load `Llama` on first call; auto-download the GGUF into `models/` on first run if missing; expose `generate(user, system, json_mode)` (uses `response_format={"type": "json_object"}`) and `model_name()`.
- [x] **Route `chat()`** (`backend/llm.py`) — If `LLM_API_KEY` set → existing cloud path; else → `local_llm.generate`. Add `model_name()` helper.
- [x] **De-hardcode model names** — Replace hardcoded `"deepseek-v4-flash"` in `backend/summarizer.py` and `backend/main.py` with `backend.llm.model_name()`.
- [x] **One-topic update** (`backend/update.py`) — `run_update(topic: str | None)`; ingest + classify always run, but summarization runs only for the given topic (or all topics when called from CLI with no topic).
- [x] **Update state** (`backend/update_state.py`) — `start_update(topic=None)` stores topic; stage string shows `summarization:<topic>`; status endpoint returns topic.
- [x] **API** (`backend/main.py`) — `POST /api/update?topic=agtech` accepts optional `topic` and passes it through.
- [x] **Frontend** (`frontend/app.js` + `index.html`) — `update-btn` sends `POST /api/update?topic=${state.topic}`; status text shows `Updating <topic>: <stage>`; refresh pill on completion.
- [x] **Tests** — Update existing update/digest/api tests; add tests for `chat()` local-vs-cloud routing, topic pass-through to update, and local-model JSON fallback.
- [x] **Docs** — Update README: local model first-run download, env vars, one-topic update behavior.

## Notes / tradeoffs
- 0.5B model gives brief but usable summaries; quality can be improved later by swapping to the 1.5B GGUF (just change `LOCAL_MODEL_URL`/`LOCAL_MODEL_PATH`).
- First run downloads ~400 MB once into `models/` (gitignored); afterwards fully offline.
- Fresh-install summarization of an entire topic is slow on CPU (many articles); steady-state updates (only new articles) are small. The `limit=500` per-topic cap stays.
