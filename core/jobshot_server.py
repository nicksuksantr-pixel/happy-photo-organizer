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

from . import jobshot
from . import jobshot_index as index
from . import jobshot_receive as receive
from .catalog import JobCatalog
from .version import read_version

# How long §4 waits for a job that is still arriving or being filed before it
# answers 409 `receiving: true` instead. Under the phone's 30 s, so it hears an
# answer rather than timing out; and every JobShot version refuses to upload on
# any status but 200 and 404, so a 409 is safe on phones already shipped
# (agreed with JobShot 2026-10-30). Never a reason to answer 404 for a job that
# is landing. A single 15-photo job filed in about 16 s when this was set.
PROBE_HOLD_SECONDS = 20.0


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "HappyPhotoOrganizer"     # no Python version advertised
    sys_version = ""
    # Seconds a socket read may wait for the next bytes (R5, reviver round 1).
    # None - the stdlib default - let a phone that left the Wi-Fi mid-upload
    # (no FIN, no RST) hold its thread, and the update, until HPO restarted.
    # Per read, not per upload: a slow link that keeps moving is not cut off.
    timeout = 60

    # ─── plumbing ───

    def handle(self):
        """One connection. A client that went quiet past `timeout`, or went
        away, ends it without a traceback: there is nobody left to answer."""
        try:
            super().handle()
        except (TimeoutError, ConnectionError):
            self.close_connection = True
        except OSError as e:
            # after a timed-out read the socket file refuses every later read
            # ("cannot read from timed out object") - the keep-alive loop's next
            # request line included
            if "timed out" not in str(e):
                raise
            self.close_connection = True

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
        ready = r.dest_root() is not None
        body = {
            "jobshot": receive.PROTOCOL,
            # **Displayed, not compared** - corrected 2026-10-02 when JobShot
            # measured their own reader. This comment used to say the phone "may
            # compare it", which I had guessed and never checked; I then quoted
            # my own guess into a test docstring as JobShot's measurement.
            #
            # What actually happens to it: `'$app $version · $ship'` is printed
            # to Nick in three places on JobShot's Settings screen. Nothing
            # compares it. So changing this string changes a sentence NICK READS,
            # which is the opposite of the licence the old comment gave.
            # (What JobShot does compare: `jobshot`, `ship`, and `ready`.)
            "app": "happy-photo-organizer",
            "version": read_version(),
            "ship": r.ship(),
            "ready": ready,
        }
        if not ready:
            # §2: the phone shows the reason and does not send. Saying it here
            # means Nick learns "choose a destination folder" before he waits
            # for an upload, rather than after.
            body["reason"] = "no destination folder chosen on the PC yet"
        self._send(200, body)

    def _job_receipt(self):
        """`GET /jobshot/v1/job/<job_id>` — the answer that makes a lost reply
        survivable, and lets the phone skip an upload it already completed."""
        if not self._authorised():
            self._send(401, {"jobshot": receive.PROTOCOL, "error": "pair first"})
            return
        from urllib.parse import unquote

        job_id = unquote(self.path[len(receive.JOB_PATH_PREFIX):]).strip("/")
        r = self.server.receiver                # type: ignore[attr-defined]
        dest_root = r.dest_root()
        entry = index.lookup(job_id, dest_root)
        if entry is None and index.is_filing(job_id):
            # The job is landing right now: its receipt is written when the
            # filing ends. Answering 404 here sent the whole job again
            # (measured 2026-10-30), so wait for the filing and answer then.
            r._log(f"receipt for {job_id}: being filed now - holding the answer")
            if not index.wait_while_filing(job_id, PROBE_HOLD_SECONDS):
                self._send(409, {"jobshot": receive.PROTOCOL, "filed": False,
                                 "receiving": True, "job_id": job_id})
                return
            entry = index.lookup(job_id, r.dest_root())
        if entry is None:
            # 404 means "not filed here" — the phone keeps its copy, which is
            # the safe direction to be wrong in.
            body = {"jobshot": receive.PROTOCOL, "filed": False,
                    "job_id": job_id}
            # ...unless this PC cannot read some of its own job records, when
            # "not filed" may really be "cannot tell". The phone asks this
            # BEFORE an upload, so a damaged job.json answered plainly here
            # means the whole job is sent and filed twice. Same field, same
            # meaning as the sidecar route's 404 (2026-10-02); added here
            # 2026-10-30 on Nick's go. The status stays 404: that is the contract.
            if dest_root is not None and index.valid_job_id(job_id):
                hurt = jobshot.unreadable_manifests(Path(dest_root))
                if hurt:
                    body["unreadable_records"] = len(hurt)
                    r._log(f"receipt for {job_id}: no record, and "
                           f"{len(hurt)} job record(s) cannot be read")
                    for bad in hurt:
                        r._log(f"  unreadable job record: {bad}")
            self._send(404, body)
            return
        self._send(200, {
            "jobshot": receive.PROTOCOL,
            "filed": True,
            "job_id": job_id,
            "folder": entry.get("folder", ""),
            "photos": entry.get("photos", 0),
            # The sidecars this job filed, under the names they are on disk as.
            # §3 has carried this since v1.053; without it here, the route that
            # exists for a lost reply could say the photos are safe and stay
            # silent about the report draft — the one file Nick typed by hand.
            # Added v1.054 on JobShot's vote (CHAIN-2026-09-26-01).
            "extras": list(entry.get("extras") or []),
            "filed_at": entry.get("filed_at", ""),
        })


    def _sidecar(self):
        """`POST /jobshot/v1/sidecar` — LAN_PROTOCOL v1.1.

        Replace a sidecar on a job already filed, without re-sending a photo.
        Every decision lives in `receive.replace_sidecars`, including which HTTP
        code to answer with: this method is the socket and nothing else, which
        is the same split the upload path uses and for the same reason.
        """
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
        if length > receive.MAX_SIDECAR_TOTAL * 2:
            self._drain()
            # Refused on the header, before a byte is read. The x2 is slack for
            # JSON overhead around the bodies; the real per-file and total caps
            # are applied to the serialised content inside.
            self._send(413, {"jobshot": receive.PROTOCOL,
                             "error": "too big for a sidecar update"})
            return
        try:
            raw = self.rfile.read(length)
        except OSError:
            return                              # the phone will retry
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            # Deliberately broad. A body of 6000 nested brackets - 4 KB, under
            # every cap - raises RecursionError, which is NOT a ValueError, so
            # the narrow version let it escape the handler: the client got a
            # closed socket with no status line at all and nothing reached
            # HPO's log. The phone cannot tell that from a dropped link, which
            # is the one distinction pairing depends on. Two reviewers
            # reproduced it, 2026-10-02.
            self._send(422, {"jobshot": receive.PROTOCOL,
                             "error": "body is not JSON"})
            return
        if not isinstance(body, dict):
            self._send(422, {"jobshot": receive.PROTOCOL,
                             "error": "body is not a JSON object"})
            return
        if body.get("jobshot") != receive.PROTOCOL:
            self._send(409, {"jobshot": receive.PROTOCOL,
                             "error": f"this PC speaks jobshot "
                                      f"{receive.PROTOCOL}"})
            return

        r = self.server.receiver                # type: ignore[attr-defined]
        try:
            result = receive.replace_sidecars(
                str(body.get("job_id", "")), body.get("files"), r.dest_root())
        except Exception as e:                  # never let a request kill the app
            r._log(f"sidecar failed: {type(e).__name__}: {str(e)[:160]}")
            self._send(500, {"jobshot": receive.PROTOCOL,
                             "error": "the PC could not apply the correction"})
            return
        if result.ok:
            note = f" ({result.error})" if result.error else ""
            r._log(f"sidecar replaced in {result.folder}: "
                   f"{', '.join(result.replaced)}{note}")
        else:
            # Logged, not swallowed - and the unreadable-record case especially,
            # because that one is Nick's archive telling him something is wrong
            # with a folder and nobody else is going to notice.
            r._log(f"sidecar refused ({result.status}): {result.error}")
            for bad in result.unreadable:
                r._log(f"  unreadable job record: {bad}")
        self._send(result.status, result.to_reply())

    def do_POST(self):                         # noqa: N802
        # Counted for the updater, which must not close the app mid-request -
        # but only a request that carries the token (R5, reviver round 1): any
        # host on the LAN could otherwise hold every update off by opening a
        # POST and never finishing it. Both routes check this same token, and
        # a refused request is drained and answered uncounted.
        counted = (self.path in (receive.UPLOAD_PATH, receive.SIDECAR_PATH)
                   and self._authorised())
        if counted:
            index.begin_receiving()
        try:
            self._post()
        finally:
            if counted:
                index.end_receiving()

    def _post(self):
        if self.path == receive.SIDECAR_PATH:
            self._sidecar()
            return
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
            claimed = int(self.headers.get("X-JobShot-Jobs", "0"))
        except ValueError:
            claimed = 0

        # LAN_PROTOCOL v1.1.1: the jobs this upload says it carries are held
        # from the first byte, so §4 does not answer 404 for them while a large
        # body is still crossing the link. Released in `finally`, whatever
        # happens - a broken upload filed nothing, and its retry must be free.
        named, why = receive.named_job_ids(
            self.headers.get(receive.JOB_IDS_HEADER), claimed)
        if why:
            r._log(why)
        held = index.begin_filing(named)
        try:
            self._receive_upload(r, dest, length, claimed, held)
        finally:
            index.end_filing(held)

    def _receive_upload(self, r, dest, length: int, claimed: int,
                        named: list[str]) -> None:
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

        answered = {str(j.get("job_id", "")) for j in result.filed + result.skipped}
        for job_id in named:
            if job_id not in answered:
                r._log(f"{receive.JOB_IDS_HEADER} named {job_id}, "
                       f"but it was not filed from this upload")

        # §3 sends X-JobShot-Jobs. Silence is not success: if the zip claimed
        # more jobs than we accounted for, say so rather than let one vanish
        # between the two lists.
        accounted = len(result.filed) + len(result.skipped)
        if claimed and accounted < claimed:
            result.warnings.append(
                f"the upload said it held {claimed} job(s) and {accounted} "
                f"were accounted for")

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
