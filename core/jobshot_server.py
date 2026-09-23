"""
jobshot_server.py — the socket half of the LAN receiver.

Deliberately thin. Everything that decides anything lives in
`jobshot_receive.py`, which is testable by calling a function with a hostile
zip; this file only moves bytes and says no early.

Shape of the thing:

  • It runs **while HPO is open**. Not a service, not a fourth app to maintain —
    the phone already queues when nothing is listening, so "HPO closed" is a
    state that already works.
  • It listens on **one LAN address**, not on everything the machine has.
  • Every request must carry the token from the pairing QR. A PC that has never
    shown a QR has no token, and `verify_token` refuses when there is none — so
    an unpaired PC accepts nothing at all.
  • Two routes exist. Anything else is 404 with no body: no file serving, no
    directory listing, no error page that says what is installed.

The vessel Wi-Fi has other people's equipment on it. This code assumes every
byte arriving is hostile until `jobshot_receive` has said otherwise.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

from . import jobshot_index as index
from . import jobshot_receive as receive
from .catalog import JobCatalog
from .version import read_version


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "HappyPhotoOrganizer"     # no Python version advertised
    sys_version = ""

    # ─── plumbing ───

    def log_message(self, fmt, *args):         # noqa: N802 (stdlib signature)
        """stderr is not where this belongs — a frozen app has none."""
        receiver = getattr(self.server, "receiver", None)
        if receiver is not None:
            receiver._log(f"{self.address_string()} {fmt % args}")

    # How much of a body we are willing to read only to throw away, so that a
    # refusal can be *delivered*. Answering a POST without draining it makes
    # Windows reset the connection mid-send, and the phone then cannot tell
    # "wrong token" from "the Wi-Fi dropped" — the one distinction pairing
    # depends on. Bounded, because draining is also how you get someone to
    # upload half a gigabyte to a PC that already said no.
    DRAIN_LIMIT = 8 * 1024 * 1024

    def _drain(self):
        """Swallow a refused request's body so the client can read the reply."""
        try:
            remaining = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return
        remaining = min(remaining, self.DRAIN_LIMIT)
        while remaining > 0:
            chunk = self.rfile.read(min(remaining, 64 * 1024))
            if not chunk:
                break
            remaining -= len(chunk)

    def _send(self, code: int, payload: dict | None = None):
        body = json.dumps(payload or {}).encode("utf-8") if payload else b""
        if code >= 400:
            # Do not keep a connection alive after a refusal: the sender may
            # still have bytes in flight that we are never going to read.
            self.close_connection = True
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if code >= 400:
            self.send_header("Connection", "close")
        self.end_headers()
        if body:
            self.wfile.write(body)
        try:
            self.wfile.flush()
        except OSError:
            pass

    def _authorised(self) -> bool:
        return receive.verify_token(self.headers.get(receive.TOKEN_HEADER, ""))

    # ─── routes ───

    def _not_found(self):
        """A 404 that names the routes. The one client that will ever hit this
        is a phone built against an older path, and "unknown route" alone would
        send someone hunting through Wi-Fi settings for a spelling mistake."""
        self._send(404, {
            "jobshot": receive.PROTOCOL,
            "error": "unknown route",
            "upload": receive.UPLOAD_PATH,
            "ping": receive.PING_PATH,
        })

    def do_GET(self):                          # noqa: N802
        if self.path.startswith(receive.JOB_PATH_PREFIX):
            self._job_receipt()
            return
        if self.path not in receive.PING_PATHS:
            self._not_found()
            return
        if not self._authorised():
            self._send(401, {"jobshot": receive.PROTOCOL, "error": "pair first"})
            return
        r = self.server.receiver                # type: ignore[attr-defined]
        self._send(200, {
            "jobshot": receive.PROTOCOL,
            "app": "Happy Photo Organizer",
            "version": read_version(),
            "ship": r.ship(),
            "ready": r.dest_root() is not None,
        })

    def _job_receipt(self):
        """`GET /jobshot/v1/job/<job_id>` — the answer that makes a lost reply
        survivable, and lets the phone skip an upload it already completed."""
        if not self._authorised():
            self._send(401, {"jobshot": receive.PROTOCOL, "error": "pair first"})
            return
        from urllib.parse import unquote

        job_id = unquote(self.path[len(receive.JOB_PATH_PREFIX):]).strip("/")
        r = self.server.receiver                # type: ignore[attr-defined]
        entry = index.lookup(job_id, r.dest_root())
        if entry is None:
            # 404 means "not filed here" — the phone keeps its copy, which is
            # the safe direction to be wrong in.
            self._send(404, {"jobshot": receive.PROTOCOL, "filed": False,
                             "job_id": job_id})
            return
        self._send(200, {
            "jobshot": receive.PROTOCOL,
            "filed": True,
            "job_id": job_id,
            "folder": entry.get("folder", ""),
            "photos": entry.get("photos", 0),
            "filed_at": entry.get("filed_at", ""),
        })

    def do_POST(self):                         # noqa: N802
        if self.path != receive.UPLOAD_PATH:
            self._drain()
            self._not_found()
            return
        if not self._authorised():
            self._drain()
            self._send(401, {"jobshot": receive.PROTOCOL, "error": "pair first"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length <= 0:
            self._send(411, {"jobshot": receive.PROTOCOL, "error": "no body"})
            return
        if length > receive.MAX_ZIP_BYTES:
            # Refused on the header, before a byte of it is read: a sender
            # cannot make this PC hold half a gigabyte just by claiming to.
            self._send(413, {"jobshot": receive.PROTOCOL,
                             "error": f"too big ({length // 1048576} MB)"})
            return

        r = self.server.receiver                # type: ignore[attr-defined]
        dest = r.dest_root()
        if dest is None:
            self._drain()
            self._send(409, {"jobshot": receive.PROTOCOL,
                             "error": "no destination folder chosen on the PC yet"})
            return

        try:
            data = self.rfile.read(length)
        except OSError as e:
            r._log(f"upload aborted: {str(e)[:120]}")
            return                              # the phone will retry

        try:
            result = receive.receive_zip(
                data, dest,
                quarantine_root=r.quarantine_root,
                expected_ship=r.ship(),
                catalog=r.catalog,
            )
        except Exception as e:                  # never let a request kill the app
            r._log(f"receive failed: {type(e).__name__}: {str(e)[:160]}")
            self._send(500, {"jobshot": receive.PROTOCOL,
                             "error": "the PC could not process the upload"})
            return

        r._notify(result)
        self._send(200 if result.ok else 422, result.to_reply())


class JobShotReceiver:
    """Owns the listening socket. Start it when HPO opens, stop it on exit.

    `dest_root` and `ship` are callables rather than values: Nick can change the
    destination in the app while the receiver is running, and the next upload
    should land in the new place without restarting anything.
    """

    def __init__(
        self,
        *,
        dest_root: Callable[[], Path | None],
        ship: Callable[[], str],
        quarantine_root: Path,
        catalog: JobCatalog | None = None,
        on_result: Callable[[receive.ReceiveResult], None] | None = None,
        on_log: Callable[[str], None] | None = None,
        port: int = receive.DEFAULT_PORT,
        host: str = "",
    ) -> None:
        self.dest_root = dest_root
        self.ship = ship
        self.quarantine_root = quarantine_root
        self.catalog = catalog
        self._on_result = on_result
        self._on_log = on_log
        self.port = port
        self.host = host
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    # ─── lifecycle ───

    def start(self) -> tuple[bool, str]:
        """Returns (ok, error). A port already in use is a plain message, not a
        traceback — it usually means a second copy of HPO is open."""
        if self.running:
            return True, ""
        host = self.host or receive.local_ip()
        try:
            self.quarantine_root.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return False, f"cannot prepare the quarantine folder — {str(e)[:100]}"

        try:
            server = ThreadingHTTPServer((host, self.port), _Handler)
        except OSError:
            # The usual cause is a second copy of HPO, or something else that
            # wanted 8765. Falling back to a port the OS picks keeps the feature
            # working — and because the QR is built from `self.port` AFTER this,
            # the phone is told the port we actually got. A QR carrying the
            # number we wanted would pair a phone to nothing, and the failure
            # would look like a network fault.
            try:
                server = ThreadingHTTPServer((host, 0), _Handler)
            except OSError as e:
                return False, f"cannot listen on {host} — {str(e)[:100]}"
        self.port = server.server_address[1]
        server.daemon_threads = True
        server.receiver = self                  # type: ignore[attr-defined]
        self._server = server
        self.host = host
        self._thread = threading.Thread(
            target=server.serve_forever, kwargs={"poll_interval": 0.2},
            name="jobshot-receiver", daemon=True)
        self._thread.start()
        self._log(f"listening on http://{host}:{self.port}")
        return True, ""

    def ensure_started(self) -> tuple[bool, str]:
        """Start if it is not already listening. The pairing dialog calls this:
        a QR is only worth showing if there is something behind it."""
        if self.running:
            return True, ""
        return self.start()

    def stop(self) -> None:
        server, self._server = self._server, None
        if server is None:
            return
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass
        self._thread = None
        self._log("stopped")

    @property
    def running(self) -> bool:
        return self._server is not None

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}" if self.running else ""

    # ─── callbacks, never allowed to break a request ───

    def _log(self, message: str) -> None:
        if self._on_log is None:
            return
        try:
            self._on_log(message)
        except Exception:
            pass

    def _notify(self, result: receive.ReceiveResult) -> None:
        if self._on_result is None:
            return
        try:
            self._on_result(result)
        except Exception:
            pass
