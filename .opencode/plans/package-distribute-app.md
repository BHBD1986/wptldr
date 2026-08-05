# Plan: Package & distribute WP TLDR for non-technical users

**Goal:** Share the app as double-click desktop apps for **Windows** and **Apple Silicon Macs**, built automatically by GitHub Actions and published as **GitHub Releases**, so non-technical users just download → install → run.

## Decisions (confirmed)
- **Model**: downloaded on first launch into a user data folder (keeps installers ~100MB instead of ~550MB; the existing auto-download mechanism is reused).
- **Signing**: none — document the one-time SmartScreen / Gatekeeper bypass in plain language.
- **Macs**: Apple Silicon only (prebuilt `arm64` wheel confirmed on the wheel index).
- **GitHub**: create a new repo (e.g. `wptldr`) via `gh` CLI and push.

## Approach
PyInstaller builds a native app per OS → GitHub Actions builds both on every release tag → attaches installers to **GitHub Releases**. Users get one link for Windows, one for Mac. The app opens a small "WP TLDR" window, auto-launches their browser at `http://127.0.0.1:<port>`, and stores its data/model in a writable per-user folder.

## Tasks
- [x] **Runtime paths** — Make `backend/config.py` also read process env vars (env overrides `.env`); add `backend/runtime_paths.py` that resolves a user app-data dir (`%LOCALAPPDATA%\WPTLDR` on Windows, `~/Library/Application Support/WPTLDR` on Mac) and points `DB_PATH`/`LOCAL_MODEL_PATH` there; fix the frozen-app `frontend/` static-mount path in `backend/main.py` (`sys._MEIPASS`).
- [x] **Launcher** (`backend/launcher.py`) — Start uvicorn on a free localhost port in a background thread; show a small tkinter window (status text, "Open browser", "Quit"); auto-open the browser when ready; show "Downloading AI model…" on first launch; graceful shutdown; windowed (no console).
- [x] **PyInstaller spec** (`packaging/WPTLDR.spec`) — onedir build; collect `llama_cpp` native libs and uvicorn/fastapi hidden imports; bundle `frontend/` as data; model intentionally excluded (downloaded at runtime).
- [x] **Windows installer** — NSIS/Inno Setup script that packages the onedir build into `WPTLDR-Setup-vX.exe` with a Desktop/Start-menu shortcut (zip fallback if installer tooling proves flaky in CI).
- [x] **macOS packaging** — PyInstaller `.app` bundle, zipped for distribution (drag to Applications).
- [x] **GitHub Actions** (`.github/workflows/release.yml`) — matrix `[windows-latest, macos-latest]`; build via spec; **smoke-test the packaged binary** (`/api/health`); package (setup .exe / mac .app zip); attach to a GitHub Release on `v*` tags (plus manual `workflow_dispatch`).
- [x] **Repo & remote** — `gh auth status`, create repo via `gh repo create`, add remote, push.
- [x] **Local verification (Windows)** — Build with PyInstaller here, run the exe, verify health endpoint and that first-launch model download + summarization work from the packaged app.
- [x] **Install guide** — `INSTALL_GUIDE.md` in plain English (which file to download, one-time security bypass, first-run model download, how to open/quit, how to update) + auto-generated Release notes pointing to it.
- [ ] **Docs/cleanup** — README packaging section; `.gitignore` for `dist/`, `build/`, `*.spec` outputs.

## Tradeoffs / caveats
- **Unsigned apps**: users see one warning — Windows *More info → Run anyway*; macOS *right-click → Open*. Documented step-by-step; no cert cost.
- **First launch** needs internet for the ~470MB model download; summaries then work offline. Fetching new articles always needs internet.
- **Intel Macs** unsupported for now (no prebuilt wheel; can add a source-compile build later if needed).
- **GitHub Releases**: public repo = free unlimited Actions minutes (private repos have a monthly allowance).
