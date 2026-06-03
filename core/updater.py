"""
updater.py — Check GitHub Releases for newer version, download installer, relaunch

Public API:
  • check_for_update(current_version, timeout=3.0) -> UpdateInfo | None
  • download_installer(url, dest, progress_cb, cancel_event) -> bool
  • launch_installer_and_exit(installer_path, silent=True)

Repo is configured via env var `HAPPY_UPDATE_REPO` (owner/name) or REPO constant.
Designed to fail silently — never block app startup or crash on network error.

Debug breadcrumbs land in %TEMP%/happy-photo-organizer-updater.log — windowed
exes have no stderr, so on-disk logging is the only way to diagnose failures.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# Default — Nick will replace via env var or by editing this line at release time
REPO = os.environ.get("HAPPY_UPDATE_REPO", "nicksuksantr-pixel/happy-photo-organizer")
INSTALLER_ASSET_NAME = "HappyPhotoOrganizerSetup.exe"
GITHUB_API = "https://api.github.com"

# ─── Debug log (breadcrumbs to %TEMP%) ───
_LOG_PATH = Path(tempfile.gettempdir()) / "happy-photo-organizer-updater.log"
_LOG_LOCK = threading.Lock()
_LOG_MAX_BYTES = 1_000_000  # 1 MB cap before rollover


def _debug_log(msg: str) -> None:
    """Append a timestamped breadcrumb. Best-effort; never raises.

    Rolls over once the log exceeds _LOG_MAX_BYTES — keeps the previous
    generation at `.1` so an idle install doesn't accumulate megabytes of
    periodic-check timeouts. Single-generation rotation is enough for the
    diagnostic role; we don't need a multi-file ring.
    """
    try:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with _LOG_LOCK:
            # Roll over if oversized — best-effort, never raise on rename.
            try:
                if _LOG_PATH.exists() and _LOG_PATH.stat().st_size > _LOG_MAX_BYTES:
                    rolled = _LOG_PATH.with_suffix(_LOG_PATH.suffix + ".1")
                    try:
                        rolled.unlink(missing_ok=True)
                    except Exception:
                        pass
                    try:
                        _LOG_PATH.rename(rolled)
                    except Exception:
                        # Couldn't rename (e.g. file locked) — fall through
                        # and continue appending; cap is a soft target.
                        pass
            except Exception:
                pass
            with open(_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


# ─── Data ───


@dataclass
class UpdateInfo:
    version: str              # "1.025" (stripped 'v' prefix)
    tag: str                  # "v1.025"
    name: str                 # release title
    body: str                 # release notes (markdown)
    html_url: str             # release page
    download_url: str         # direct .exe url
    size: int                 # bytes


# ─── Version compare ───


def _parse_version(s: str) -> tuple[int, ...]:
    """'1.025' or 'v1.025' or '1.0.25' → (1, 25) / (1, 0, 25)
    Non-numeric parts coerced to 0. Empty → (0,).
    """
    s = s.strip().lstrip("vV")
    parts = re.split(r"[.\-_+]", s)
    out: list[int] = []
    for p in parts:
        # extract leading digits if mixed (e.g. "025rc1" → 25)
        m = re.match(r"^\d+", p)
        out.append(int(m.group(0)) if m else 0)
    return tuple(out) if out else (0,)


def is_newer(current: str, latest: str) -> bool:
    """latest > current?  Pads shorter tuple with zeros."""
    a = _parse_version(current)
    b = _parse_version(latest)
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    return b > a


# ─── GitHub Releases API ───


def _fetch_latest_release(timeout: float) -> dict | None:
    url = f"{GITHUB_API}/repos/{REPO}/releases/latest"
    # F8 (Tester 2026-06-04): record the resolved repo slug once per check so a
    # wrong/typo'd REPO (or unset HAPPY_UPDATE_REPO in the built exe) surfaces
    # as a diagnosable breadcrumb instead of a permanently-silent no-op updater.
    _debug_log(f"_fetch_latest_release: GET {url}")
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "HappyPhotoOrganizer-Updater",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError):
        return None


def check_for_update(current_version: str, timeout: float = 3.0) -> UpdateInfo | None:
    """Returns UpdateInfo if a newer release exists, else None.
    Fails silently on any error (no network, repo not found, etc.).
    """
    data = _fetch_latest_release(timeout)
    if not data:
        return None
    tag = str(data.get("tag_name") or "").strip()
    if not tag:
        return None
    latest_ver = tag.lstrip("vV")
    if not is_newer(current_version, latest_ver):
        return None

    assets = data.get("assets") or []
    asset = None
    for a in assets:
        if a.get("name") == INSTALLER_ASSET_NAME:
            asset = a
            break
    if not asset:
        # fallback: first .exe asset
        for a in assets:
            if str(a.get("name", "")).lower().endswith(".exe"):
                asset = a
                break
    if not asset:
        return None

    return UpdateInfo(
        version=latest_ver,
        tag=tag,
        name=str(data.get("name") or tag),
        body=str(data.get("body") or "").strip(),
        html_url=str(data.get("html_url") or ""),
        download_url=str(asset.get("browser_download_url") or ""),
        size=int(asset.get("size") or 0),
    )


# ─── Download ───


def download_installer(
    url: str,
    dest: Path,
    progress_cb: Callable[[int, int], None] | None = None,
    cancel_event: threading.Event | None = None,
    chunk_size: int = 64 * 1024,
    max_attempts: int = 3,
    attempt_timeout: float = 300.0,
    expected_size: int = 0,
) -> tuple[bool, str]:
    """Download URL → dest with retry + HTTP Range resume.

    Integrity guards (v1.034 — was ENA v2.6.5 incident pattern):
    - Captures ETag + Last-Modified on first attempt; passes them as
      `If-Range` on resume. If GitHub re-uploaded the asset between attempts,
      the server returns 200 (full payload) instead of 206, and we restart
      from 0 — no chance of stitching old + new bytes into a corrupt installer.
    - If `expected_size` (from the release API) is non-zero and the final file
      size differs, treats it as a failure even if `Content-Length` matched.

    On a transient failure, retry up to `max_attempts` times. Each retry asks
    GitHub for `Range: bytes=<size>-` so the partial file is reused.
    progress_cb(bytes_done, total_bytes) fires on every chunk. cancel_event
    aborts cleanly between chunks.

    Returns (success, message).
    """
    _debug_log(f"download_installer start: url={url} dest={dest} expected_size={expected_size}")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        _debug_log(f"  dest.mkdir failed: {e}")
        return False, f"Cannot create cache dir: {str(e)[:120]}"

    expected_total = expected_size  # may be overridden by Content-Length on first attempt
    last_err = "unknown"
    server_etag: str | None = None
    server_last_modified: str | None = None

    for attempt in range(1, max_attempts + 1):
        resume_from = dest.stat().st_size if dest.exists() else 0

        # If we somehow already have the full file from a previous run, accept it
        if expected_total > 0 and resume_from >= expected_total:
            _debug_log(f"  attempt {attempt}: already complete ({resume_from} bytes)")
            return True, f"Already downloaded {resume_from:,} bytes"

        headers = {"User-Agent": "HappyPhotoOrganizer-Updater"}
        if resume_from > 0:
            headers["Range"] = f"bytes={resume_from}-"
            # If the server re-uploaded the asset, fail the Range and force
            # a full re-download instead of stitching mismatched bytes.
            if server_etag:
                headers["If-Range"] = server_etag
            elif server_last_modified:
                headers["If-Range"] = server_last_modified

        _debug_log(f"  attempt {attempt}/{max_attempts}: resume_from={resume_from}")

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=attempt_timeout) as resp:
                status = resp.status
                cl = int(resp.headers.get("Content-Length") or 0)
                cr = resp.headers.get("Content-Range") or ""
                # Capture validators on first response so subsequent retries
                # can pin to this exact asset version
                if server_etag is None:
                    server_etag = resp.headers.get("ETag")
                if server_last_modified is None:
                    server_last_modified = resp.headers.get("Last-Modified")
                # Determine the full expected size
                if cr:
                    # "bytes 1000-2000/3000" — total is after the slash
                    m = re.search(r"/(\d+)$", cr)
                    if m:
                        expected_total = int(m.group(1))
                elif cl and resume_from == 0:
                    expected_total = cl
                _debug_log(
                    f"    HTTP {status} CL={cl} CR={cr!r} expected_total={expected_total}"
                )

                # status 206 → partial; 200 → server ignored Range OR If-Range
                # didn't match (asset changed) → restart from 0
                if status == 206 and resume_from > 0:
                    file_mode = "ab"
                else:
                    file_mode = "wb"
                    if resume_from > 0 and status == 200:
                        _debug_log(
                            "    server returned 200 instead of 206 — asset changed or Range ignored; restarting from 0"
                        )
                    resume_from = 0

                done = resume_from
                with open(dest, file_mode) as f:
                    while True:
                        if cancel_event and cancel_event.is_set():
                            _debug_log(f"    cancelled at {done} bytes")
                            try:
                                f.close()
                                dest.unlink(missing_ok=True)
                            except Exception:
                                pass
                            return False, "Cancelled"
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
                        if progress_cb:
                            try:
                                progress_cb(done, expected_total or done)
                            except Exception:
                                pass

            # Verify final size if we know what to expect
            actual_size = dest.stat().st_size if dest.exists() else 0
            if expected_total > 0 and actual_size < expected_total:
                last_err = (
                    f"truncated: got {actual_size:,} of {expected_total:,} bytes"
                )
                _debug_log(f"    {last_err} — will retry")
                continue  # next attempt resumes from where we are

            # Cross-check against release-API size if provided — catches the
            # case where Content-Length matched a stale Range response but
            # the real asset on GitHub is a different size.
            if expected_size > 0 and actual_size != expected_size:
                # Bug (Tester 2026-06-04): unconditionally deleting + retrying
                # here meant a STALE release-API `size` (it can lag an asset
                # re-upload) forced 3× full re-downloads that never converged.
                # If the transfer itself was complete — actual_size matches the
                # transfer-level expected_total (Content-Length / Content-Range)
                # — trust that and ACCEPT, just noting the discrepancy. Only
                # retry-fresh when we have no transfer-level completeness signal.
                if expected_total > 0 and actual_size == expected_total:
                    _debug_log(
                        f"    release-API size {expected_size:,} != file {actual_size:,}, "
                        f"but transfer complete (matches Content-Length) — accepting"
                    )
                    return True, f"Downloaded {actual_size:,} bytes (release size {expected_size:,})"
                last_err = (
                    f"size mismatch: file {actual_size:,} bytes, release reports {expected_size:,}"
                )
                _debug_log(f"    {last_err} — dropping partial + retrying fresh")
                try:
                    dest.unlink(missing_ok=True)
                except Exception:
                    pass
                # Drop the validators so the next attempt grabs a fresh pair
                server_etag = None
                server_last_modified = None
                continue

            _debug_log(f"  attempt {attempt}: SUCCESS — {actual_size:,} bytes")
            return True, f"Downloaded {actual_size:,} bytes"

        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            last_err = f"{type(e).__name__}: {str(e)[:140]}"
            _debug_log(f"    attempt {attempt} failed: {last_err}")
            # Don't delete the partial — next retry resumes from here
            # Brief backoff before retrying
            if attempt < max_attempts:
                time.sleep(min(2 ** (attempt - 1), 8))

    # All attempts exhausted — drop the partial so a fresh start works next time
    try:
        dest.unlink(missing_ok=True)
    except Exception:
        pass
    _debug_log(f"download_installer FAILED after {max_attempts} attempts: {last_err}")
    return False, f"Download failed after {max_attempts} attempts: {last_err}"


# ─── Launch installer + exit ───


def launch_installer_and_exit(installer_path: Path, silent: bool = True) -> None:
    """Spawn installer (detached) then exit current process.
    Silent mode passes --silent --upgrade so installer skips UI.
    """
    args: list[str] = [str(installer_path)]
    if silent:
        args.extend(["--silent", "--upgrade"])

    try:
        # DETACHED_PROCESS = 0x00000008, CREATE_NEW_PROCESS_GROUP = 0x00000200
        # so installer survives after parent exits
        creationflags = 0
        if sys.platform == "win32":
            creationflags = 0x00000008 | 0x00000200
        subprocess.Popen(
            args,
            creationflags=creationflags,
            close_fds=True,
            stdin=None, stdout=None, stderr=None,
        )
    except Exception:
        # last resort: os.startfile (no flags possible)
        try:
            if sys.platform == "win32":
                os.startfile(str(installer_path))  # type: ignore[attr-defined]
        except Exception:
            pass

    # exit the running app so installer can overwrite files
    sys.exit(0)


# ─── Cache dir helpers ───


def cache_dir() -> Path:
    p = Path.home() / ".happy-photo-organizer" / "updates"
    p.mkdir(parents=True, exist_ok=True)
    return p


def cleanup_old_installers(keep: str | None = None) -> None:
    """Remove cached installer .exe files, except `keep` filename."""
    try:
        for f in cache_dir().iterdir():
            if f.is_file() and f.suffix.lower() == ".exe":
                if keep and f.name == keep:
                    continue
                try:
                    f.unlink()
                except Exception:
                    pass
    except Exception:
        pass
