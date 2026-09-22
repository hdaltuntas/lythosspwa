"""
lythosspwa.web.server — the local HTTP server that serves the interface.

The interface runs as a small HTTP server on the machine it was started on and
is driven from the browser. That choice makes the program usable over a remote
session or inside a container — no display for a desktop toolkit to find — and
brings in nothing beyond the standard library.

The server stays on the loopback address unless the host is changed on purpose.
Long computations (a parametric or reliability study) run in a thread, so the
interface keeps answering while several hundred samples are analysed.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .. import APP_NAME, __version__
from .session import Session
from .strings import shell_strings

STATIC = os.path.join(os.path.dirname(__file__), "static")

#: A mark for the browser tab: a wall holding back the ground behind it
_FAVICON = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    b'<rect width="32" height="32" rx="6" fill="#1E1F24"/>'
    b'<path d="M4 12h11v16H4z" fill="#C9A876"/>'
    b'<path d="M17 4v24" stroke="#2F80ED" stroke-width="3" stroke-linecap="round"/>'
    b'<path d="M19 20h9v8h-9z" fill="#56CCF2" opacity="0.55"/>'
    b'<path d="M15 9h-9" stroke="#F2994A" stroke-width="2" stroke-linecap="round"/></svg>'
)

#: File names of the report and export downloads
REPORT_TYPES = {"pdf": "application/pdf",
                "html": "text/html; charset=utf-8",
                "docx": "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document"}
EXPORT_TYPES = {"csv": "text/csv; charset=utf-8",
                "xlsx": "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"}

SESSION = Session()


class Handler(BaseHTTPRequestHandler):
    server_version = "LythosSPWA"

    def log_message(self, fmt, *args):        # leave the console to the analysis
        pass

    # ---------------------------------------------------------------- helpers
    def _send(self, code: int, body: bytes, content_type: str, extra: dict = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, code: int = 200) -> None:
        self._send(code, json.dumps(payload, default=float).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _static(self, name: str) -> None:
        path = os.path.join(STATIC, os.path.basename(name))
        if not os.path.isfile(path):
            return self._json({"error": "not found"}, 404)
        kinds = {".html": "text/html; charset=utf-8",
                 ".js": "text/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml"}
        with open(path, "rb") as fh:
            self._send(200, fh.read(),
                       kinds.get(os.path.splitext(path)[1], "application/octet-stream"))

    def _download(self, name: str, body: bytes, content_type: str) -> None:
        self._send(200, body, content_type,
                   {"Content-Disposition": f'attachment; filename="{name}"'})

    # --------------------------------------------------------------------- GET
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route, query = parsed.path, parse_qs(parsed.query)
        try:
            if route in ("/", "/index.html"):
                return self._static("index.html")
            if route.startswith("/static/"):
                return self._static(route)
            if route == "/favicon.ico":
                return self._send(200, _FAVICON, "image/svg+xml")
            if route == "/api/meta":
                return self._json(SESSION.meta())
            if route == "/api/state":
                return self._json(SESSION.state())
            if route == "/api/study":
                return self._json(SESSION.study_payload())
            if route == "/api/plot":
                target = query.get("target", ["analysis"])[0]
                kind = query.get("kind", ["net_pressure"])[0]
                output = query.get("output", [""])[0]
                return self._send(200, SESSION.plot(target, kind, output), "image/png")
            self._json({"error": "not found"}, 404)
        except Exception as exc:
            self._json({"error": f"{exc}"}, 400)

    # -------------------------------------------------------------------- POST
    def do_POST(self) -> None:
        route = urlparse(self.path).path
        try:
            data = self._body()
            if route == "/api/language":
                SESSION.set_language(str(data.get("lang", "en")))
                return self._json(SESSION.meta())
            if route == "/api/theme":
                return self._json({"theme": SESSION.set_theme(str(data.get("theme", "light")))})
            if route == "/api/analyse":
                return self._json(SESSION.analyse(data.get("values", {})))
            if route == "/api/variables":
                return self._json(SESSION.study_variables(data.get("values", {})))
            if route == "/api/study":
                return self._json(SESSION.start_study(data.get("values", {})))
            if route == "/api/cancel":
                return self._json(SESSION.cancel())
            if route == "/api/project":
                return self._project(data)
            if route == "/api/load":
                return self._json(SESSION.load_project(data.get("project", {})))
            if route == "/api/report":
                return self._report(data)
            if route == "/api/export-study":
                return self._export_study(data)
            self._json({"error": "not found"}, 404)
        except Exception as exc:
            self._json({"error": f"{exc}"}, 400)

    # ----------------------------------------------------------------- actions
    def _project(self, data: dict) -> None:
        """The inputs as a downloadable project file."""
        payload = json.dumps(SESSION.project_file(data.get("values", {})),
                             indent=2, ensure_ascii=False).encode("utf-8")
        self._download("project.spwa", payload, "application/json; charset=utf-8")

    def _report(self, data: dict) -> None:
        """Writes the report to a temporary file and sends it as a download."""
        fmt = str(data.get("format", "pdf")).lower()
        if fmt not in REPORT_TYPES:
            return self._json({"error": f"unknown report format: {fmt}"}, 400)
        name = f"lythosspwa_report.{fmt}"
        with tempfile.TemporaryDirectory() as tmp:
            path = SESSION.report(fmt, os.path.join(tmp, name))
            with open(path, "rb") as fh:
                body = fh.read()
        self._download(name, body, REPORT_TYPES[fmt])

    def _export_study(self, data: dict) -> None:
        """The sampled study table as CSV or XLSX."""
        kind = str(data.get("format", "csv")).lower()
        if kind not in EXPORT_TYPES:
            return self._json({"error": f"unknown export format: {kind}"}, 400)
        name = f"lythosspwa_study.{kind}"
        with tempfile.TemporaryDirectory() as tmp:
            path = SESSION.export_study(kind, os.path.join(tmp, name))
            with open(path, "rb") as fh:
                body = fh.read()
        self._download(name, body, EXPORT_TYPES[kind])


def serve(host: str = "127.0.0.1", port: int = 8779, open_browser: bool = True,
          lang: str = "en") -> None:
    """Starts the interface and serves it until Ctrl+C."""
    SESSION.set_language(lang)
    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    strings = shell_strings(SESSION.lang)
    print(f"{APP_NAME} {__version__} — {url}")
    print(strings["stop_hint"])
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n" + strings["stopped"])
    finally:
        server.server_close()
