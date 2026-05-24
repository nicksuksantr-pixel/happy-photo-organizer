"""
update_worker.py — Auto-update lifecycle owner.

A standalone worker that polls GitHub Releases, downloads installers in the
background, and triggers the silent install. All update-related state lives
on this object; the host (typically the main app window) only needs to expose
a small contract.

Host contract — the constructor's `host` argument must provide:
  - host.after(ms: int, callback) -> id_token        # Tk scheduler
  - host.after_cancel(id_token)
  - host.log(msg: str, level: str = "ok")            # write to UI log
  - host.is_batch_running -> bool                    # property
  - host.on_before_install()                         # set teardown flag

Design notes:
  - Periodic check fires every UPDATE_INTERVAL_MS (5 min) and survives the
    window being hidden in the tray — the Tk mainloop keeps running.
  - manual_check() does NOT touch the schedule, so the tray "Check now" menu
    item doesn't shorten the cadence.
  - All worker callbacks marshal back to the Tk thread via host.after(0, ...).
  - is_batch_running gates downloads AND installs — if a batch is running we
    only log the discovery and defer. resume_deferred() picks it up later.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

from core import auth

if TYPE_CHECKING:
    from core.updater import UpdateInfo


class UpdateWorker:
    """Owns auto-update state. One per app instance."""

    UPDATE_INTERVAL_MS = 5 * 60 * 1000  # 5 minutes
    FIRST_CHECK_DELAY_MS = 3_000         # snappy first paint

    def __init__(self, host, current_version: str) -> None:
        self.host = host
        self.current_version = current_version

        # Pending state (set when a check finds something, cleared when applied)
        self.pending_installer: Path | None = None
        self.pending_installer_version: str | None = None
        self.pending_info: UpdateInfo | None = None  # download deferred mid-batch

        # Bookkeeping
        self._after_id = None
        self.in_progress = False  # True while a download is actively running
        # Track last poll outcome so we only log GitHub reachability state
        # transitions (ok→fail / fail→ok), not every 5-min poll while down.
        # Round-6 BUG-M6 (Cos review 2026-05-24).
        self._last_poll_ok: bool | None = None

    # ─── Public lifecycle ────────────────────────────────────

    def start(self) -> None:
        """Kick off the periodic check. Respects auth.auto_check_updates."""
        cfg = auth.load_config()
        if not cfg.get("auto_check_updates", True):
            return
        self._after_id = self.host.after(self.FIRST_CHECK_DELAY_MS, self.tick)

    def cancel(self) -> None:
        """Stop the periodic check. Idempotent."""
        if self._after_id is not None:
            try:
                self.host.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def tick(self) -> None:
        """One tick of the periodic schedule: poll + reschedule."""
        threading.Thread(target=self._poll_github, daemon=True).start()
        self._after_id = self.host.after(self.UPDATE_INTERVAL_MS, self.tick)

    def manual_check(self) -> None:
        """User-triggered check (tray 'Check for updates now'). Does NOT touch
        the schedule — the next periodic tick still fires on time.
        """
        threading.Thread(target=self._poll_github, daemon=True).start()

    def resume_deferred(self) -> None:
        """Call after a batch ends. Resumes whichever stage was deferred."""
        if self.host.is_batch_running:
            return  # safety — should not happen
        if self.pending_installer and self.pending_installer.exists():
            v = self.pending_installer_version or "?"
            self.host.log(f"Batch done — installing pending update v{v}", "ok")
            self._install_now(v)
            return
        info = self.pending_info
        if info is not None:
            self.pending_info = None
            self.host.log(f"Batch done — resuming update v{info.version}", "ok")
            self._begin_download(info)

    # ─── Internals ───────────────────────────────────────────

    def _poll_github(self) -> None:
        """Background thread. Hits GitHub /releases/latest and dispatches back
        to the Tk loop. Only logs on reachability state transitions.
        """
        ok = False
        try:
            from core import updater
            info = updater.check_for_update(self.current_version, timeout=5.0)
            ok = True
            if info is not None:
                self.host.after(0, lambda i=info: self._on_available(i))
        except Exception:
            ok = False
        # State-transition logging only (round-6 BUG-M6) — avoids
        # 'update check failed' every 5 min while GitHub / DNS is down.
        prev = self._last_poll_ok
        self._last_poll_ok = ok
        if prev is None:
            return  # first poll — don't log either outcome
        if prev and not ok:
            self.host.after(0, lambda: self.host.log("Update check: GitHub unreachable", "warn"))
        elif ok and not prev:
            self.host.after(0, lambda: self.host.log("Update check: GitHub reachable again", "ok"))

    def _on_available(self, info) -> None:
        """Update found. Dedup → if download in progress: defer-new-tag only →
        else defer-if-batch / download.

        v1.034 fix (BUG-1): the v1.033 in_progress short-circuit dropped a
        *different* new tag discovered mid-download. Now we dedup the same tag
        first, then if a different tag arrives during download we stash it as
        pending_info so resume_deferred picks it up after the active download
        completes (or after the batch ends).
        """
        # Dedup same version FIRST — avoid noisy re-logs across ticks regardless
        # of in_progress / batch state.
        if self.pending_info is not None and self.pending_info.tag == info.tag:
            return
        if self.pending_installer and self.pending_installer_version == info.version:
            return

        # If a download is already running, this is necessarily a *different*
        # tag (we deduped above). Stash it so the worker picks it up after the
        # current download finishes — don't kick off a second download here.
        if self.in_progress:
            self.pending_info = info
            self.host.log(
                f"Update available: v{info.version} — queued (download already in progress)",
                "ok",
            )
            return

        self.host.log(f"Update available: v{info.version}", "ok")

        if self.host.is_batch_running:
            self.pending_info = info
            self.host.log(
                "  -> deferred — will download + install after the current batch finishes",
                "ok",
            )
            return
        self._begin_download(info)

    def _begin_download(self, info) -> None:
        """Kick off a silent background download of the installer."""
        self.host.log(f"Downloading v{info.version} in background...", "ok")
        self.in_progress = True

        def worker():
            from core import updater
            dest = updater.cache_dir() / f"HappyPhotoOrganizerSetup-v{info.version}.exe"
            ok, msg = updater.download_installer(
                info.download_url, dest,
                expected_size=info.size,
            )
            self.in_progress = False
            if ok:
                self.host.after(0, lambda d=dest, v=info.version: self._on_ready(d, v))
            else:
                self.host.after(
                    0,
                    lambda m=msg: self.host.log(f"Update download failed: {m}", "warn"),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _on_ready(self, installer_path: Path, version: str) -> None:
        """Download finished — install, defer, or download a newer pending tag."""
        # If a newer tag arrived during this download, drop the just-downloaded
        # installer and start fetching the newer one. Cheaper than installing
        # then immediately re-running the update.
        #
        # Compare against pending_info.version (already stripped of leading
        # 'v' / 'V' by updater.parse) instead of tag.lstrip("vV") — pre-release
        # tags like '1.035-rc1' would otherwise mismatch the parsed version
        # '1.035' and trigger a redundant re-download loop.
        # Round-6 BUG-H2 (Cos review 2026-05-24).
        if self.pending_info is not None and self.pending_info.version != version:
            try:
                from core import updater
                if updater.is_newer(version, self.pending_info.version):
                    newer = self.pending_info
                    self.pending_info = None
                    # Clean the now-outdated installer
                    try:
                        installer_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    self.host.log(
                        f"v{version} downloaded but v{newer.version} arrived during download — fetching newer",
                        "ok",
                    )
                    if self.host.is_batch_running:
                        self.pending_info = newer
                        return
                    self._begin_download(newer)
                    return
            except Exception:
                pass

        self.pending_installer = installer_path
        self.pending_installer_version = version
        # The lighter "info-only" pending marker is superseded by a ready file
        self.pending_info = None

        if self.host.is_batch_running:
            self.host.log(
                f"Update v{version} downloaded — will install after current batch",
                "ok",
            )
            return
        self._install_now(version)

    def _install_now(self, version: str | None = None) -> None:
        """Launch installer (silent) and exit. Guarded against mid-batch fire."""
        if self.host.is_batch_running:
            return
        if not self.pending_installer or not self.pending_installer.exists():
            return
        try:
            from core import updater
            self.host.log(
                f"Installing update{f' v{version}' if version else ''}...",
                "ok",
            )
            self.host.on_before_install()  # let host set its teardown flag
            updater.launch_installer_and_exit(self.pending_installer, silent=True)
        except SystemExit:
            raise
        except Exception as e:
            self.host.log(f"Install failed: {str(e)[:120]}", "warn")
