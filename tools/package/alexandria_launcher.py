#!/usr/bin/env python3
"""Alexandria — desktop launcher. Serves the library from a local copy and opens it in its own app window.

    Alexandria.exe              (built with "Build Alexandria.exe.bat")   or   python alexandria_launcher.py
    Alexandria.exe --update     refresh the local copy from GitHub (PxD2/cog) first, then open
    Alexandria.exe --lan        also serve it to the laptops / Pi 5s on this network

The local copy lives next to the program in "library\\" (a mirror of the GitHub repo: app + COG packs + 3D sets).
It works with no internet at all; with internet it can update itself. Standard library only.
"""
from __future__ import annotations

import argparse, http.server, io, json, os, shutil, socket, socketserver, subprocess, sys, threading, time, urllib.request, webbrowser, zipfile
from pathlib import Path

REPO = "PxD2/cog"
APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
LIB = APP_DIR / "library"
BUNDLED = Path(getattr(sys, "_MEIPASS", APP_DIR)) / "library"      # a copy packed inside the .exe, used the first time


def log(*a):
    print("[Alexandria]", *a, flush=True)


def update_from_github() -> bool:
    """Download the repo as a zip (public; a token is used if one is set) and replace the local copy."""
    url = f"https://codeload.github.com/{REPO}/zip/refs/heads/main"
    hdr = {"User-Agent": "Alexandria-launcher"}
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        url, hdr["Authorization"] = f"https://api.github.com/repos/{REPO}/zipball/main", f"Bearer {tok}"
    try:
        log("updating from GitHub…")
        with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=120) as r:
            data = r.read()
        tmp = APP_DIR / "library.new"
        shutil.rmtree(tmp, ignore_errors=True)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            root = z.namelist()[0].split("/")[0]
            for m in z.infolist():
                rel = m.filename[len(root) + 1:]
                if not rel or m.is_dir() or rel.startswith(("tools/", ".")):
                    continue
                out = tmp / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(z.read(m))
        shutil.rmtree(LIB, ignore_errors=True)
        tmp.rename(LIB)
        (LIB / ".updated").write_text(time.strftime("%Y-%m-%d %H:%M"))
        log("library updated")
        return True
    except Exception as e:      # noqa: BLE001
        log("update skipped:", e)
        return False


def ensure_library(update: bool):
    if update or not (LIB / "alexandria" / "index.html").exists():
        if not update_from_github() and not (LIB / "alexandria" / "index.html").exists() and BUNDLED.exists() and BUNDLED != LIB:
            log("using the copy packed inside the program")
            shutil.copytree(BUNDLED, LIB, dirs_exist_ok=True)
    if not (LIB / "alexandria" / "index.html").exists():
        raise SystemExit("No library found. Connect to the internet once and run: Alexandria.exe --update")


class Quiet(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".glb": "model/gltf-binary", ".webmanifest": "application/manifest+json",
                      ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json"}

    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(LIB), **k)

    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def free_port(start=8790):
    for p in range(start, start + 40):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return 0


def open_app_window(url: str):
    """Open as an app window (Edge / Chrome --app), else the default browser."""
    cands = []
    if sys.platform.startswith("win"):
        pf = [os.environ.get(k, "") for k in ("ProgramFiles(x86)", "ProgramFiles", "LocalAppData")]
        cands = [Path(b) / "Microsoft/Edge/Application/msedge.exe" for b in pf] + [Path(b) / "Google/Chrome/Application/chrome.exe" for b in pf]
    else:
        cands = [Path(shutil.which(x) or "") for x in ("chromium", "google-chrome", "microsoft-edge")]
    for c in cands:
        if c and c.is_file():
            subprocess.Popen([str(c), f"--app={url}", "--start-maximized"])
            return
    webbrowser.open(url)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--lan", action="store_true")
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args(argv)
    ensure_library(a.update)
    port = free_port()
    host = "0.0.0.0" if a.lan else "127.0.0.1"
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    srv = socketserver.ThreadingTCPServer((host, port), Quiet)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://localhost:{port}/alexandria/"
    log("serving", url, "(also on this network)" if a.lan else "")
    if not a.no_open:
        open_app_window(url)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
