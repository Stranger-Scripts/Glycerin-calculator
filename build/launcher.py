"""
build/launcher.py
~~~~~~~~~~~~~~~~~
Entry point used by the PyInstaller bundle.

Imports the FastAPI `app` defined in `glycerin_calculator.main` without
modification, opens a browser to the served URL, and runs uvicorn in the
foreground with reload disabled (reload uses a child watcher process that
does not work inside a frozen bundle).

This file is NOT imported when running the project normally via
`uv run glycerin-calculator`. Use `glycerin_calculator.main:run` for that.
"""

from __future__ import annotations

import threading
import time
import webbrowser

import uvicorn

from glycerin_calculator.main import app

HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"


def _open_browser_when_ready() -> None:
    # Small delay so uvicorn has time to bind the port before the browser
    # tries to connect. 1.2s is generous; the import time of the bundle is
    # the dominant cost.
    time.sleep(1.2)
    webbrowser.open(URL)


def main() -> None:
    print(f"Glycerin Calculator running at {URL}")
    print("Close this window to stop the server.")
    threading.Thread(target=_open_browser_when_ready, daemon=True).start()
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
