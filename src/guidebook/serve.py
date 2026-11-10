"""Optional local server: shows the built guide and gives its "Check and update" button something to talk to.

Safety: binds to 127.0.0.1 only; checks the Host header (blocks DNS rebinding); the update call is POST-only, needs the
X-Guidebook header (a browser form on another site cannot set it) and an Origin that matches. The button runs `update`
WITHOUT the model unless the server was started with model=True. Without this server the static guide still works."""
import json
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .config import load_config
from .engine import status, update

LOOPBACK = ("127.0.0.1", "localhost", "::1")


class _Handler(SimpleHTTPRequestHandler):
    server_version = "guidebook"

    def __init__(self, *a, project=None, model=False, lock=None, **kw):
        self.project, self.model, self.lock = project, model, lock
        super().__init__(*a, **kw)

    def log_message(self, fmt, *args):      # quiet: no per-request noise, nothing about the visitor is stored
        pass

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").rsplit(":", 1)
        port_ok = len(host) == 2 and host[1] == str(self.server.server_address[1])
        return port_ok and host[0].strip("[]") in LOOPBACK

    def _json(self, code, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._host_ok():
            return self._json(403, {"error": "bad host"})
        if self.path.split("?")[0] == "/__guidebook/status":
            try:
                return self._json(200, status(self.project).as_dict())
            except Exception as e:      # a broken config must not crash the server
                return self._json(500, {"error": str(e)})
        return super().do_GET()

    def do_HEAD(self):
        if not self._host_ok():
            return self._json(403, {"error": "bad host"})
        return super().do_HEAD()

    def do_POST(self):
        if not self._host_ok():
            return self._json(403, {"error": "bad host"})
        if self.path.split("?")[0] != "/__guidebook/update":
            return self._json(404, {"error": "not found"})
        origin = self.headers.get("Origin")
        if self.headers.get("X-Guidebook") != "1" or (origin and origin.split("://", 1)[-1] != self.headers.get("Host")):
            return self._json(403, {"error": "missing or wrong guard header"})
        with self.lock:
            try:
                rep = update(self.project, no_model=not self.model)
            except Exception as e:
                return self._json(500, {"error": str(e)})
        return self._json(200, {"written": rep.written, "proposed": rep.proposed, "built": rep.built, "calls": rep.calls, "nothing_to_do": rep.nothing_to_do,
                                "status": status(self.project).as_dict()})

    def do_PUT(self):
        self._json(405, {"error": "method not allowed"})

    do_DELETE = do_PATCH = do_PUT


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):      # the browser went away mid-reply (page reload): not an error
            return
        super().handle_error(request, client_address)


def make_server(project, port=8765, model=False, host="127.0.0.1") -> ThreadingHTTPServer:
    if host not in LOOPBACK:
        raise ValueError("guidebook serve only binds to 127.0.0.1 (never to a public address)")
    root = Path(project).resolve()
    out = root / load_config(root).output
    if not (out / "index.html").is_file():
        raise FileNotFoundError(f"no built guide in {out}; run `guidebook build` first")
    handler = partial(_Handler, directory=str(out), project=str(root), model=model, lock=threading.Lock())
    return _Server((host, port), handler)
