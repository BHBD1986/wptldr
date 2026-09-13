# Plan: Make v2 downloads/upgrades include the latest summaries

## Overview

The v0.2.0 release assets already contain the fresh seed (CI smoke test seeded
1,833 articles through 2026-09-11). The real bug is app-side: `seed_db()` in
`backend/runtime_paths.py` only copies the bundled seed when the user DB is
missing/empty and never overwrites a populated DB. Users upgrading from v0.1.0
(seed ends 2026-08-06, "first week of August") keep their old database, so
summaries appear stale. This plan makes the launcher sync a newer bundled seed
into the user DB, preserving locally generated data, and cuts a new release.

## Approach

On launch, if the bundled seed is newer than the user's DB (compared by
`MAX(published_at)`), sync the newer seed's rows into the user DB using SQLite
`ATTACH` + `INSERT OR IGNORE`. Existing local data (e.g. "Go Deeper"
expansions, custom briefs) is preserved. Fall back to copying the seed when the
DB is missing/empty (current behavior). Release as v0.2.1.

## Tasks

- [x] **Add seed freshness detection** (`backend/runtime_paths.py`) — helper `seed_max_date(path)` returning `MAX(published_at)` (fallback: article count) and `seed_is_newer(seed, target) -> bool`.
- [x] **Implement `sync_seed()`** (`backend/runtime_paths.py`) — backup user DB to `wptldr.db.bak`; `ATTACH` seed DB; `INSERT OR IGNORE` into `articles`, `article_topics`, `summaries`, `digests`; prefer bundled summaries for articles the seed contains (upsert); leave `expansions` untouched.
- [x] **Wire into launcher** (`backend/launcher.py`) — replace the two `seed_db()` call sites with an `ensure_seed()` that seeds when empty, else syncs when newer, and logs counts. Dev (`not frozen`) stays a no-op.
- [x] **Keep first-run path** — `seed_db()` still handles the empty/missing case; new DB gets a plain copy.
- [x] **Tests** (`tests/test_runtime_paths.py`) — newer seed triggers sync; equal/older seed no-op; new articles/summaries appear; existing rows and `expansions` preserved; `.db.bak` created; dev no-op.
- [x] **Version + release** — bump defaults in `packaging/WPTLDR.spec`, `packaging/package.py`, `packaging/WPTLDR.iss` to 0.2.1; commit, push, tag v0.2.1, let CI rebuild both platforms.
- [x] **Clean stale local build** (`dist/` is gitignored but holds an Aug-6 seed) — rebuild/remove so local packaging cannot ship stale data.
- [x] **Docs** (`README.md`) — note that upgrading automatically applies newer bundled data and keeps a `.db.bak` backup.

completion_promise: V2_DATA_SYNC_FIX_COMPLETE
