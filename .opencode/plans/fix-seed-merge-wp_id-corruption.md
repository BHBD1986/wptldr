# Plan: Fix seed-merge corruption (wp_id keyed, auto-repairing)

## Overview

`backend/runtime_paths.py::sync_seed()` merges the bundled seed into the user
DB keyed on the local autoincrement `id`. When a target DB's `id -> wp_id`
mapping diverges from the seed's (after the app's **Update** or importing a
differently-ordered `.db`), summaries/topics are written onto the wrong
articles and topic counts drift (246 vs 222 agtech). Reproduced in-memory.
`backend/digest.py` trusting the model's `ref` compounds the problem.

The fix re-keys the merge on the stable `wp_id`, is idempotent and
non-destructive, forces one repair pass on corrupted installs via a seed
fingerprint, and ships as v0.2.3.

## Decisions (best practice)

1. Reconciliation scope - non-destructive, `wp_id`-keyed reconcile of
   seed-matched articles; preserve user-only articles, `expansions`, and custom
   briefs.
2. Release - new **v0.2.3** tag (never mutate a published release's assets).
3. Repair trigger - one-time **seed fingerprint marker** stored in a `meta`
   table, so the corrected merge runs exactly once per dataset.

## Tasks

- [x] **Re-key `sync_seed()` on `wp_id`** — insert missing articles by `wp_id`; map `seed.articles.id -> target.id` via `wp_id` for `summaries`; rebuild `article_topics` (delete + re-insert mapped seed topics); prefer bundled `digests` via `INSERT OR REPLACE`. Never touch `expansions`.
- [x] **Add `meta` table + seed fingerprint** — store the bundled fingerprint (max date, article/summary counts, byte size); `ensure_seed()` seeds on first run, else runs the corrected merge when the fingerprint changed (or target is empty), then writes the marker.
- [x] **Harden digest key stories** — in `backend/digest.py`, drop/sanitize key stories whose `ref` isn't a real item and always derive the title from the referenced item.
- [x] **Tests** — divergent-id fixture proving correct `wp_id` mapping; repair removes mis-assigned topic rows; idempotency (second run no-op); fingerprint change triggers exactly one sync; digest ref sanitization. Run full `pytest`.
- [x] **Data** — seed already correct (1,837 / 1,837, 222 agtech); re-verify after repair.
- [x] **Release** — bump packaging to 0.2.3, commit, push, tag `v0.2.3`, CI build, publish draft as Latest.
- [x] **Docs** — note bundled data is reconciled by `wp_id` and upgrades auto-repair mismatched installs (incl. manual mitigations: Import data, or delete `%LOCALAPPDATA%\WPTLDR\wptldr.db`).

completion_promise: FIX_SEED_MERGE_WP_ID_COMPLETE
