# Plan: Sep 12 full summary refresh & re-release v0.2.2

## Overview

Refresh WP TLDR data through 2026-09-12, guarantee that **every** bundled
article has a summary across all six topics, regenerate year-to-date topic
briefs through 2026-09-12, and re-release as **v0.2.2** (replacing the existing
assets). Decisions: replace v0.2.2 assets, fill gaps + new summaries only,
refresh all 6 YTD briefs.

Key facts:
- `seed/wptldr.db` is currently 100% covered (1,833 articles / 1,833
  summaries, max date 2026-09-11); id 1613 already has a summary.
- The stale data users see is in old local copies (Aug 5, 1,578 articles);
  the v0.2.x seed-sync on launch repairs them.
- The WP API returns 4 new Sep 12 articles.
- `backend/summarize.py` filters `word_count > 80`, which caused prior gaps.

## Approach

Ingest through Sep 12 -> classify -> summarize every article lacking a
summary (short ones included, all six topics) with DeepSeek V4 Flash ->
regenerate Jan 1 -> Sep 12 briefs for all topics -> verify 100% coverage ->
copy to seed -> move the `v0.2.2` tag and re-publish.

## Tasks

- [x] **Ingest Sep 12** — `python -m backend.ingest --start 2026-09-11 --end 2026-09-12`; confirm the 4 new posts land.
- [x] **Classify** — `python -m backend.classify`; assert every article has >=1 topic.
- [x] **Guarantee summary coverage** — update `backend/summarize.py` to drop the `word_count > 80` gate and add a coverage pass selecting all articles without a summary across every topic (fall back to title+excerpt when content is very short); run with DeepSeek V4 Flash env overrides for all six topics.
- [x] **Refresh all 6 YTD briefs** — set `DIGEST_MAX_ITEMS` high enough to avoid truncation (crops has 1,041 YTD); `backend.digest --topic <t> --from 2026-01-01 --to 2026-09-12 --force` for all topics; drop stale `to_date=2026-09-11` YTD rows.
- [x] **Verify coverage** — assert `articles LEFT JOIN summaries` = 0, per-topic `articles == summarized`, max `published_at` is a Sep 12 article, and 6 fresh briefs exist.
- [x] **Ship data** — WAL checkpoint, copy `data/wptldr.db` -> `seed/wptldr.db`, re-verify coverage in the seed.
- [x] **Tests** — add a test that the summarize coverage pass includes short (`word_count <= 80`) articles; run full `pytest`.
- [x] **Re-release v0.2.2** — delete the published `v0.2.2` release, delete local+remote tag, commit data/code, re-tag `v0.2.2` on the new commit, push the tag, let CI build, then publish the new draft as Latest.
- [x] **Docs** — note that every bundled article ships with a summary and briefs are current through the release date.

## Caveats

- Replacing assets under the same `v0.2.2` tag means users who already
  installed v0.2.2 are not prompted to re-download; only fresh installs and
  reinstalls get the refresh.
- "Fill gaps + new only" leaves existing summaries untouched; only new/missing
  articles get fresh LLM output.

completion_promise: SEP12_FULL_SUMMARY_REFRESH_COMPLETE
