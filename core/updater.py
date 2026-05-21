"""
updater.py — Check GitHub Releases for newer version, download installer, relaunch

Public API:
  • check_for_update(current_version, timeout=3.0) -> UpdateInfo | None
  • download_installer(url, dest, progress_cb, cancel_event) -> bool
  • launch_installer_and_exit(installer_path, silent=True)

Repo is configured via env var `HAPPY_UPDATE_REPO` (owner/name) or REPO constant.
Designed to fail silently — never block app startup or crash on network error.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# Default — Nick will replace via env var or by editing this line at release time
REPO = os.environ.get("HAPPY_UPDATE_REPO", "nicksuksantr-pixel/happy-photo-organizer")
INSTALLER_ASSET_NAME = "HappyPhotoOrganizerSetup.exe"
GITHUB_API = "https://api.github.com"


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
) -> tuple[bool, str]:
    """Download URL → dest. progress_cb(bytes_done, total_bytes).
    Returns (success, message). Cancels cleanly if cancel_event is set.
    """
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        # remove stale partial
        if dest.exists():
            try:
                dest.unlink()
            except Exception:
                pass

        req = urllib.request.Request(
            url, headers={"User-Agent": "HappyPhotoOrganizer-Updater"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            with open(dest, "wb") as f:
                while True:
                    if cancel_event and cancel_event.is_set():
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
                            progress_cb(done, total)
                        except Exception:
                            pass
        return True, f"Downloaded {done:,} bytes"
    except Exception as e:
        try:
            dest.unlink(missing_ok=True)
        except Exception:
            pass
        return False, f"Download failed: {str(e)[:200]}"


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
