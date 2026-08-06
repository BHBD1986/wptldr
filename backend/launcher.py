"""Desktop launcher for the packaged WP TLDR app.

Starts the FastAPI server on a free localhost port, shows a small status
window, downloads the AI model on first run, and opens the user's browser
once the server is ready. Closing the window stops the app.
"""

import logging
import os
import sys
import threading
import webbrowser

import uvicorn

from backend.main import app as fastapi_app
from backend.runtime_paths import app_data_dir, configure_settings, seed_db

logger = logging.getLogger("wptldr")


def _setup_logging() -> None:
    log_dir = app_data_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(str(log_dir / "launcher.log"), encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.info("launcher starting")


def _ensure_stdio() -> None:
    """Windowed builds have no console (sys.stdout is None); give uvicorn
    and any print() calls a safe sink so they don't crash."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")


def find_free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def resolve_port() -> int:
    """Port to listen on; WPTLDR_PORT overrides the random free port."""
    import os

    override = os.environ.get("WPTLDR_PORT")
    if override:
        return int(override)
    return find_free_port()


def run_server(port: int):
    config = uvicorn.Config(
        fastapi_app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    server.run()
    return server


def _run_tk() -> None:
    import tkinter as tk

    _ensure_stdio()
    _setup_logging()
    configure_settings()
    if seed_db():
        logger.info("seeded app-data DB from bundled 2026 dataset")
    port = resolve_port()
    url = f"http://127.0.0.1:{port}"

    root = tk.Tk()
    root.title("WP TLDR")
    root.geometry("440x240")
    root.resizable(False, False)

    status = tk.Label(
        root,
        text="Starting…",
        font=("TkDefaultFont", 11),
        wraplength=390,
        justify="left",
    )
    status.pack(padx=22, pady=24)

    buttons = tk.Frame(root)
    buttons.pack(pady=8)
    tk.Button(buttons, text="Open Browser", width=16,
              command=lambda: webbrowser.open(url)).pack(side="left", padx=8)
    tk.Button(buttons, text="Quit", width=16,
              command=root.destroy).pack(side="left", padx=8)

    state = {"opened": False}

    def set_status(text: str) -> None:
        root.after(0, lambda: status.configure(text=text))

    server = {"ref": None}

    def _start():
        try:
            config = uvicorn.Config(
                fastapi_app, host="127.0.0.1", port=port, log_level="warning"
            )
            srv = uvicorn.Server(config)
            server["ref"] = srv
            logger.info("server starting on port %s", port)
            srv.run()
            logger.info("server stopped")
        except Exception:  # noqa: BLE001
            logger.exception("server failed")

    threading.Thread(target=_start, daemon=True).start()

    def poll() -> None:
        if not state["opened"] and server["ref"] is not None and server["ref"].started:
            state["opened"] = True
            webbrowser.open(url)
            set_status("WP TLDR is running.\n\n"
                       "Your browser should have opened. Keep this window open "
                       "while you use it, then click Quit when done.")
        root.after(400, poll)

    root.after(400, poll)
    root.mainloop()


def _run_console() -> None:
    """Fallback when tkinter is unavailable (dev/headless)."""
    _ensure_stdio()
    configure_settings()
    if seed_db():
        print("seeded app-data DB from bundled 2026 dataset")
    port = resolve_port()
    url = f"http://127.0.0.1:{port}"
    print(f"WP TLDR running at {url} — press Ctrl+C to stop.")
    threading.Thread(target=run_server, args=(port,), daemon=True).start()
    webbrowser.open(url)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass


def main() -> None:
    if os.environ.get("WPTLDR_CONSOLE"):
        _run_console()
        return
    try:
        import tkinter  # noqa: F401
    except ImportError:
        _run_console()
        return
    _run_tk()


if __name__ == "__main__":
    main()
