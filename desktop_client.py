"""BrilliantPay Windows desktop client for a hosted BrilliantPay server."""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


APP_NAME = "BrilliantPay"
DEFAULT_SERVER_URL = "https://brilliantpay.duckdns.org"


def config_path():
    app_data = os.environ.get("LOCALAPPDATA")
    if not app_data:
        app_data = str(Path.home() / "AppData" / "Local")
    return Path(app_data) / APP_NAME / "desktop.json"


def validate_server_url(value):
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Enter a complete server address, such as https://pay.example.com.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("The server address must not contain credentials, a query, or a fragment.")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Use HTTPS for a server on the internet.")
    return urlunsplit((
        parsed.scheme,
        parsed.netloc,
        parsed.path.rstrip("/"),
        "",
        "",
    ))


def save_server_url(path, server_url):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
            suffix=".tmp",
        ) as config_file:
            json.dump({"server_url": server_url}, config_file)
            config_file.write("\n")
            temporary_path = Path(config_file.name)
        temporary_path.replace(path)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def load_server_url(path):
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
        server_url = config.get("server_url")
        if not isinstance(server_url, str):
            raise ValueError("The saved server address is missing.")
        return validate_server_url(server_url)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError, ValueError) as error:
        raise ValueError(
            f"Could not read the saved server settings at {path}: {error}"
        ) from error


def prompt_for_server_url(initial_url):
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.title(f"{APP_NAME} — Server setup")
    root.resizable(False, False)
    root.geometry("480x190")

    frame = tk.Frame(root, padx=24, pady=20)
    frame.pack(fill="both", expand=True)
    tk.Label(
        frame,
        text="Connect to your BrilliantPay server",
        font=("Segoe UI", 13, "bold"),
    ).pack(anchor="w")
    tk.Label(
        frame,
        text="Enter the HTTPS address your team uses. Your payments and messages remain on that server.",
        justify="left",
        wraplength=430,
    ).pack(anchor="w", pady=(8, 12))
    address = tk.Entry(frame, width=58)
    address.pack(fill="x")
    address.insert(0, initial_url or DEFAULT_SERVER_URL)
    address.focus_set()

    result = {"server_url": None}

    def connect():
        try:
            result["server_url"] = validate_server_url(address.get())
        except ValueError as error:
            messagebox.showerror("Invalid server address", str(error), parent=root)
            return
        root.destroy()

    buttons = tk.Frame(frame)
    buttons.pack(anchor="e", pady=(14, 0))
    tk.Button(buttons, text="Connect", command=connect, default="active").pack(side="right")
    tk.Button(buttons, text="Cancel", command=root.destroy).pack(side="right", padx=(0, 8))
    root.bind("<Return>", lambda _event: connect())
    root.mainloop()
    return result["server_url"]


def show_error(message):
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(APP_NAME, message, parent=root)
        root.destroy()
    except (ImportError, OSError, RuntimeError):
        print(message, file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument(
        "--configure",
        action="store_true",
        help="change the BrilliantPay server address",
    )
    arguments = parser.parse_args()

    path = config_path()
    try:
        initial_url = None if arguments.configure else load_server_url(path)
        server_url = initial_url
        if server_url is None:
            server_url = prompt_for_server_url(initial_url)
        if server_url is None:
            return 0
        save_server_url(path, server_url)
    except (OSError, ValueError) as error:
        show_error(str(error))
        return 1

    try:
        import webview

        webview.create_window(
            APP_NAME,
            server_url,
            width=1440,
            height=960,
            min_size=(960, 640),
        )
        webview.start()
    except Exception as error:
        show_error(
            "BrilliantPay could not open its desktop window.\n\n"
            "Check that Microsoft Edge WebView2 Runtime is installed and that "
            "the server address is reachable.\n\n"
            f"Details: {error}"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
