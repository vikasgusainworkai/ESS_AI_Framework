#!/usr/bin/env python3
"""
User Management app  ->  http://127.0.0.1:5070

  GET    /api/users            list users
  POST   /api/users            {"empid", "username", "designation"}
  PUT    /api/users/<empid>    {"username", "designation"}
  DELETE /api/users/<empid>

The service module is reloaded whenever app/user_service.py changes, so after the AI agent
fixes a bug you only need to refresh the browser (no restart).
"""
import importlib
import json
import re
import shutil
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import user_service  # noqa: E402

HOST, PORT = "127.0.0.1", 5070
SERVICE_FILE = Path(user_service.__file__)
DATA = ROOT / "data" / "users.json"
SEED = ROOT / "data" / "seed_users.json"
INDEX = Path(__file__).resolve().parent / "static" / "index.html"
LOCK = threading.Lock()
_seen = {"mtime": SERVICE_FILE.stat().st_mtime_ns}


def service():
    """A fresh service per request (reads users.json); reloads the code if it changed on disk."""
    mtime = SERVICE_FILE.stat().st_mtime_ns
    if mtime != _seen["mtime"]:
        importlib.reload(user_service)
        _seen["mtime"] = mtime
    if not DATA.exists():
        shutil.copyfile(SEED, DATA)
    return user_service.UserService(DATA)


class Handler(BaseHTTPRequestHandler):
    server_version = "UserMgmt/1.0"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, payload, ctype="application/json; charset=utf-8"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def _handle(self, fn):
        try:
            with LOCK:
                code, payload = fn(service())
        except ValueError as e:
            code, payload = 400, {"error": str(e)}
        except KeyError as e:
            code, payload = 404, {"error": str(e.args[0])}
        except Exception as e:  # never leave the browser hanging
            code, payload = 500, {"error": f"Internal error: {e}"}
        self._send(code, payload)

    def _empid(self):
        m = re.fullmatch(r"/api/users/([^/]+)", self.path.split("?")[0])
        return unquote(m.group(1)) if m else None

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            return self._send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
        if path == "/api/users":
            return self._handle(lambda svc: (200, svc.list_users()))
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.split("?")[0] != "/api/users":
            return self._send(404, {"error": "not found"})
        b = self._body()
        self._handle(lambda svc: (201, svc.add_user(b.get("empid"), b.get("username"), b.get("designation"))))

    def do_PUT(self):
        empid = self._empid()
        if empid is None:
            return self._send(404, {"error": "not found"})
        b = self._body()
        self._handle(lambda svc: (200, svc.update_user(empid, b.get("username"), b.get("designation"))))

    def do_DELETE(self):
        empid = self._empid()
        if empid is None:
            return self._send(404, {"error": "not found"})
        self._handle(lambda svc: (200, {"deleted": svc.delete_user(empid)}))


if __name__ == "__main__":
    service()  # make sure data/users.json exists
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"User Management app running  ->  http://{HOST}:{PORT}   (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
# my own unrelated edit
