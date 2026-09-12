# Full Data & Search Update — Sep 2026

## Overview
Refresh WP TLDR Explorer end to end: broaden search, expand topic classification, run the full ingest → classify → summarize pipeline for **every** category, generate **year-to-date** (Jan 1 → today) category briefs, ship them in the bundled seed DB, and publish a **v0.2.0** release.

**Model routing decision:**
- **Bulk/shipped generation** (new article summaries + YTD briefs) uses the **DeepSeek V4 Flash API** (`https://api.deepseek.com/v1`, model `deepseek-v4-flash`, key from the existing `DEEPSEEK_API_KEY` env var) via temporary env overrides — no code change, key never written to a tracked file.
- **User-triggered generation in the app** keeps the bundled **OpenRouter** key and the existing `DIGEST_MAX_ITEMS=300` cap.

Findings that shape the work:
- Data ends **2026-08-06**; today is **2026-09-11** (~5 weeks missing).
- Topics: agtech, livestock, crops, markets, politics, unclassified.
- Search only matches **titles** (`backend/main.py:254`); unclassified = 335 articles.
- Classifier rules: `backend/classifier.py`.
- Digests cap at `DIGEST_MAX_ITEMS=300` (`backend/config.py:47`); only 2 cached, none YTD.
- `data/` is gitignored; `seed/wptldr.db` is the committed/bundled artifact. Releases build on `v*` tags.

## Tasks

- [x] **Expand classifier rules** (`backend/classifier.py`) — add more WP category slugs to `CATEGORY_RULES`/`POLITICS_CATEGORIES` (e.g. crops: `production`, `in-season`, `pre-season`, `sustainability`, `weather`; markets: `strategies`, `ag-finance`; agtech: `farm-it-manitoba`) and expand `KEYWORD_RULES` per topic (crops: drought/frost/fusarium/canola/wheat/barley; livestock: bovine/poultry/antibiotic/feed; markets: loonie/rally/basis; politics: bill/policy/carbon tax/supply management; agtech: GPS/satellite/data/software). Stays deterministic.

- [x] **Add full reclassification** (`backend/classify.py`) — `--rebuild` flag that clears `article_topics` and reclassifies **all** articles so new rules apply to existing rows; default incremental behavior preserved.

- [x] **Broaden search** (`backend/main.py`) — `list_articles` matches title **OR** content_text **OR** summary TLDR **OR** key_points **OR** categories; update the search placeholder in `frontend/index.html`.

- [x] **Keep the digest cap unchanged** (`backend/config.py`) — leave `DIGEST_MAX_ITEMS=300` as the default so OpenRouter/user-generated briefs stay capped. The higher cap is applied **only** for the one-time shipped generation via env override (next tasks).

- [x] **Run full pipeline for all categories (DeepSeek V4 Flash)** — with env overrides `LLM_BASE_URL=https://api.deepseek.com/v1`, `LLM_API_KEY=$env:DEEPSEEK_API_KEY`, `LLM_MODEL=deepseek-v4-flash`:
  - ingest `2026-08-05 → 2026-09-11`
  - `classify --rebuild`
  - `summarize --topic <t> --limit 500` for agtech, livestock, crops, markets, politics, unclassified

- [x] **Generate YTD category briefs (DeepSeek V4 Flash)** — same env overrides plus a one-run `DIGEST_MAX_ITEMS=1000` so briefs cover the full year, for all 6 categories:
  - `digest --topic <t> --from 2026-01-01 --to 2026-09-11 --force`
  - Persist in `data/wptldr.db`; `model` recorded as `deepseek-v4-flash`.

- [x] **Ship data** — checkpoint WAL, copy `data/wptldr.db` → `seed/wptldr.db`.

- [x] **Tests** — add classifier tests for new rules + `--rebuild`; add API test proving search matches body/summary (not just title); confirm default `DIGEST_MAX_ITEMS` is still 300; run `python -m pytest -q`.

- [x] **Docs** — README: broader search scope, bundled YTD briefs, and how users regenerate briefs for custom ranges via OpenRouter (300 cap).

- [x] **Publish** — commit code + seed DB, `git push origin master`, tag **v0.2.0**, push tag to trigger the installer release build.

## Notes / tradeoffs
- Env overrides are set per-process only; no secret is written to a committed file, and the app's default OpenRouter behavior is untouched.
- DeepSeek must accept `response_format={"type":"json_object"}`; if it rejects it, use the digest module's existing JSON-extraction fallback (or send `extra_body.thinking=disabled` as a one-off).
- Reclassification shifts existing topic counts; summaries are keyed by article id and are unaffected.
- YTD generation is many DeepSeek calls (6 topics × two-pass chunks); retry/backoff on rate limits.
- Copy to `seed/` only after all summaries + briefs are written; don't commit `.db.bak`/WAL sidecars.
