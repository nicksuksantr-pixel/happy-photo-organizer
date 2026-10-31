"""
install_swap.py — replace the installed app in place, with a way back (v1.066).

Shared by the installer (which swaps) and the app (which tidies up after a
swap it survived). No GUI imports: the installer bundles `core/` through its
spec's pathex.

Before v1.066 an update was `taskkill /F` the app, sleep half a second, then
`zipfile.extract` over the live tree (bug U3/U4 in bug/bug_v1.058-v1.065.md):
- a file the old version shipped and the new one does not stayed forever,
  so the tree drifted from any version that was ever built;
- a failure half way left half of each version, with no way back and no
  relaunch — the app was simply gone until someone reinstalled it by hand;
- the app was killed, whatever it was doing.

Now, under `<install dir>\\.update\\`, out of the user's sight (UPDATE_DRILL §2):

  1. wait for the app to exit by itself (it hands over, then exits). An app
     up to v1.066 never does (bug D1), so after a grace the installer ends
     exactly the process that started it, and nothing else;
  2. check the disk, then STAGE: extract the whole payload to `new\\`. A
     damaged payload fails here — zipfile checks every CRC — before a single
     installed file has been touched;
  3. write the journal (`journal.json`: the old file list, state "swapping"),
     then swap file by file. An old file is MOVED to `old\\` and the new one
     renamed into its place — except `.exe` files, which are COPIED to `old\\`
     and replaced, so the path a shortcut points at never stops existing and
     shell link tracking has no move to follow. Files the old version had and
     the new one lacks are moved to `old\\` too (pruned);
  4. any failure: put every file back from `old\\`, remove the ones that were
     added, log FAILED. A crash mid-swap is finished the same way by the next
     installer run, from the journal;
  5. success: journal state "swapped", log SWAPPED. The new build, once it has
     been running a few seconds, deletes `.update\\` (CLEANED) — the rollback
     copy lives exactly as long as it could be needed.

The pruning never reaches outside the payload's own top folder
(`HappyPhotoOrganizer\\`): `uninstall.bat`, `installed-files.json` and
`.update\\` sit beside it. From v1.066 the installer records what it put there
(`installed-files.json`), and later updates prune only files on that list —
a file the installer did not put in the tree is never deleted.
"""
from __future__ import annotations

import filecmp
import json
import os
import shutil
import sys
import time
import zipfile
from pathlib import Path
from typing import Callable

from core import update_log

UPDATE_DIR = ".update"
MANIFEST = "installed-files.json"
MUTEX_NAME = "Local\\HappyPhotoOrganizer-SingleInstance-a1b2c3d4"  # core.single_instance
WINDOW_TITLE_PREFIX = "Happy Photo Organizer"

# a locked file (antivirus, the search indexer, a process still exiting) is
# tried again for this long in total before the swap gives up and rolls back
LOCK_RETRY_SECONDS = 30.0
MAX_PATH_CHARS = 259        # Windows' MAX_PATH, less its terminating NUL
_BACKOFF = (0.2, 0.5, 1.0, 2.0, 4.0, 8.0)

ProgressCb = Callable[[float, str], None]


# ─── is the app still running? ───


def app_running() -> bool:
    """True while any process holds the app's single-instance mutex."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenMutexW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
        k32.OpenMutexW.restype = wintypes.HANDLE
        SYNCHRONIZE = 0x00100000
        h = k32.OpenMutexW(SYNCHRONIZE, False, MUTEX_NAME)
        if not h:
            return False
        k32.CloseHandle(h)
        return True
    except Exception:
        return False


def app_window_open() -> bool:
    """True if a visible Tk window titled like the app exists. Used only after
    the wait runs out, to tell an app that is really open (leave it alone)
    from one that lost its window and is only failing to exit."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        found = [False]
        Proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

        def cb(hwnd, _lp):
            cls = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(hwnd, cls, 64)
            if not cls.value.startswith("Tk"):
                return True
            n = user32.GetWindowTextLengthW(hwnd)
            if n <= 0:
                return True
            t = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, t, n + 1)
            if t.value.startswith(WINDOW_TITLE_PREFIX) and "Setup" not in t.value:
                found[0] = True
                return False
            return True

        user32.EnumWindows(Proc(cb), 0)
        return found[0]
    except Exception:
        return False


def wait_for_app_exit(timeout: float = 60.0, poll: float = 0.25) -> bool:
    """Wait for the app to let go of its mutex. True once it has."""
    deadline = time.monotonic() + timeout
    while app_running():
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll)
    return True


# ─── the app that handed over (bug D1, first drill run 2026-10-31) ───
#
# Every HPO up to v1.066 hands over and calls sys.exit(0) with its tray icon
# still running, and pystray's thread is not a daemon thread, so the process
# never ends (it waits in threading._shutdown for ever). The installers up to
# v1.065 hid that with `taskkill /F` on every HPO. These end exactly the one
# process that started the upgrade, once it has had time to exit by itself,
# and only while it is provably still that process.

_TH32CS_SNAPPROCESS = 0x00000002
_PROCESS_TERMINATE = 0x0001
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_SYNCHRONIZE = 0x00100000
_STILL_ACTIVE = 259


def _kernel32():
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                               wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    k32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    k32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k32.WaitForSingleObject.restype = wintypes.DWORD
    k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    return k32


def process_info(pid: int) -> tuple[str, int] | None:
    """(full exe path, creation time as a FILETIME number) of a live process,
    or None when it is gone or cannot be asked."""
    if sys.platform != "win32" or not pid:
        return None
    try:
        import ctypes
        from ctypes import wintypes
        k32 = _kernel32()
        h = k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not h:
            return None
        try:
            code = wintypes.DWORD()
            if not k32.GetExitCodeProcess(h, ctypes.byref(code)) or code.value != _STILL_ACTIVE:
                return None
            buf = ctypes.create_unicode_buffer(32768)
            n = wintypes.DWORD(len(buf))
            if not k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
                return None
            t = [wintypes.FILETIME() for _ in range(4)]
            if not k32.GetProcessTimes(h, *[ctypes.byref(x) for x in t]):
                return None
            return buf.value, (t[0].dwHighDateTime << 32) | t[0].dwLowDateTime
        finally:
            k32.CloseHandle(h)
    except Exception:
        return None


def parent_pid(pid: int) -> int | None:
    """The pid that started `pid`, from a process snapshot."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                        ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                        ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]

        k32 = _kernel32()
        k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        snap = k32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
        if not snap or snap == wintypes.HANDLE(-1).value:
            return None
        try:
            e = PROCESSENTRY32W()
            e.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            ok = k32.Process32FirstW(snap, ctypes.byref(e))
            while ok:
                if e.th32ProcessID == pid:
                    return int(e.th32ParentProcessID) or None
                ok = k32.Process32NextW(snap, ctypes.byref(e))
            return None
        finally:
            k32.CloseHandle(snap)
    except Exception:
        return None


def _same_file(a: str | Path, b: str | Path) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def handover_parent(app_exe: Path, max_hops: int = 3) -> dict | None:
    """The process that started this upgrade, if it is the app being replaced:
    {"pid", "exe", "created"}. Read at the start of a silent upgrade, while it
    is certainly still that process. Walks up a few hops because a one-file
    installer runs as a bootloader plus a child of it."""
    me = process_info(os.getpid())
    if me is None:
        return None
    pid = os.getpid()
    for _ in range(max_hops):
        pid = parent_pid(pid)
        info = process_info(pid) if pid else None
        if info is None:
            return None
        exe, created = info
        if created >= me[1]:
            return None             # younger than this installer: a pid used again, not its ancestor
        if _same_file(exe, app_exe):
            return {"pid": pid, "exe": exe, "created": created}
    return None


def end_handover_parent(parent: dict, timeout: float = 10.0) -> bool:
    """End `parent` (from `handover_parent`) and wait for it. Only while the
    pid still names the same exe started at the same moment: a pid used again
    is never touched. True once that process is gone."""
    info = process_info(parent["pid"])
    if info is None:
        return True
    if info != (parent["exe"], parent["created"]):
        return False
    try:
        k32 = _kernel32()
        h = k32.OpenProcess(_PROCESS_TERMINATE | _SYNCHRONIZE, False, int(parent["pid"]))
        if not h:
            return False
        try:
            k32.TerminateProcess(h, 1)
            return k32.WaitForSingleObject(h, int(timeout * 1000)) == 0
        finally:
            k32.CloseHandle(h)
    except Exception:
        return False


# ─── the swap ───


def _files_under(root: Path) -> set[str]:
    if not root.is_dir():
        return set()
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def _retry(op: Callable[[], None], deadline: float) -> None:
    """Run a filesystem op, retrying a PermissionError (a lock) with backoff
    until `deadline`. Anything else, or a lock that outlasts it, raises."""
    i = 0
    while True:
        try:
            op()
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(_BACKOFF[min(i, len(_BACKOFF) - 1)])
            i += 1


def _payload_top(names: list[str]) -> str:
    """The one top-level folder every payload file sits in. Pruning is bounded
    by it, so a payload with files at its root is refused rather than guessed
    at: its "tree" would be the whole install folder."""
    paths = [n.replace("\\", "/").strip("/") for n in names]
    paths = [n for n in paths if n]
    if not paths or any("/" not in n for n in paths):
        raise ValueError("the payload has files outside a top folder")
    tops = {n.split("/", 1)[0] for n in paths}
    if len(tops) != 1:
        raise ValueError(f"the payload must hold exactly one top folder, it holds {sorted(tops)[:5]}")
    top = tops.pop()
    if top in (".", "..", UPDATE_DIR):
        raise ValueError(f"unexpected payload top folder {top!r}")
    return top


def too_long(root: Path, names: list[str]) -> str:
    """Why files named `names` cannot be written under `root`, or "": past
    259 characters Windows refuses a path unless long paths are turned on, and
    all Python sees is a FileNotFoundError naming a file that is plainly
    there. Staging puts every file 12 characters deeper (under `.update`, then
    `new`), so it is the first thing to hit the limit (measured 2026-10-31,
    bug_v1.066)."""
    if not names:
        return ""
    n = len(str(Path(root) / max(names, key=len)))
    if n <= MAX_PATH_CHARS:
        return ""
    return (f"the install folder's path is too long for this update: {n} characters "
            f"under {root}, where Windows allows {MAX_PATH_CHARS} unless long paths "
            f"are enabled")


def _read_json(p: Path) -> dict | None:
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _write_json(p: Path, data: dict) -> None:
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def _rmtree(p: Path) -> None:
    def onerror(func, path, _exc):
        try:
            os.chmod(path, 0o666)
            func(path)
        except OSError:
            pass
    if p.exists():
        shutil.rmtree(p, onerror=onerror)


def _remove_empty_dirs(root: Path, keep: set[str]) -> None:
    """Remove directories under `root` left empty by pruning, deepest first,
    except those the new tree has."""
    if not root.is_dir():
        return
    for d in sorted((p for p in root.rglob("*") if p.is_dir()),
                    key=lambda p: len(p.parts), reverse=True):
        rel = d.relative_to(root).as_posix()
        if rel in keep:
            continue
        try:
            d.rmdir()            # only succeeds when empty
        except OSError:
            pass


def rollback(install_dir: Path, journal: dict | None = None) -> tuple[bool, str]:
    """Put the old tree back from `.update\\old\\`, per the journal. Safe to run
    twice. Returns (complete, detail)."""
    ud = install_dir / UPDATE_DIR
    journal = journal or _read_json(ud / "journal.json") or {}
    top = journal.get("top") or ""
    if not top:
        return False, "no journal to roll back from"
    target, old = install_dir / top, ud / "old" / top
    old_files = set(journal.get("old_files") or [])
    stuck: list[str] = []
    deadline = time.monotonic() + LOCK_RETRY_SECONDS
    # files the update ADDED (not in the old tree) go; the saved ones come back
    for rel in sorted(_files_under(target) - old_files):
        try:
            _retry(lambda r=rel: (target / r).unlink(), deadline)
        except OSError:
            stuck.append(rel)
    for rel in sorted(_files_under(old)):
        dst, keep = target / rel, old / rel
        try:
            # an .exe is COPIED aside before it is replaced: if the replace
            # never happened (it was locked), the original is still in place
            if dst.is_file() and filecmp.cmp(keep, dst, shallow=True):
                keep.unlink()
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            _retry(lambda k=keep, d=dst: os.replace(k, d), deadline)
        except OSError:
            stuck.append(rel)
    _remove_empty_dirs(target, {p for r in old_files for p in _parents(r)})
    if stuck:
        return False, f"{len(stuck)} file(s) could not be put back, e.g. {stuck[0]}"
    _rmtree(ud)
    return True, f"{len(old_files)} file(s) of the old version restored"


class InterruptedRollbackIncomplete(OSError):
    """An earlier interrupted swap could not be fully put back on this run."""


def recover_interrupted(install_dir: Path, to_version: str = "?") -> str:
    """Before a new swap: finish whatever an earlier run left in `.update\\`."""
    ud = install_dir / UPDATE_DIR
    if not ud.exists():
        return ""
    j = _read_json(ud / "journal.json")
    state = (j or {}).get("state")
    if state == "swapping":
        ok, detail = rollback(install_dir, j)
        if not ok:
            # `.update` is the only way back now (bug R2): swap_in keeps it
            update_log.log("FAILED", str(j.get("to_version") or to_version),
                           f"an earlier swap was interrupted and could not be rolled back yet: "
                           f"{detail}; kept {UPDATE_DIR} for the next run")
            raise InterruptedRollbackIncomplete(
                f"an earlier interrupted update could not be rolled back yet: {detail}")
        update_log.log("FAILED", str(j.get("to_version") or to_version),
                       f"an earlier swap was interrupted; rolled back on this run: {detail}")
        return "rolled back an interrupted update"
    _rmtree(ud)        # "staging", "swapped", or no journal: nothing to keep
    return f"cleared an old {UPDATE_DIR} ({state or 'no journal'})"


def swap_in(payload_zip: Path, install_dir: Path, from_version: str, to_version: str,
            progress_cb: ProgressCb | None = None) -> tuple[bool, str]:
    """Install `payload_zip` into `install_dir`, replacing what is there in
    place. Returns (ok, message). On failure the old tree is back (or the
    message says what could not be put back)."""
    def progress(frac: float, msg: str) -> None:
        if progress_cb:
            try:
                progress_cb(max(0.0, min(1.0, frac)), msg)
            except Exception:
                pass

    install_dir = Path(install_dir)
    ud = install_dir / UPDATE_DIR
    infos: list[zipfile.ZipInfo] = []
    try:
        install_dir.mkdir(parents=True, exist_ok=True)
        recover_interrupted(install_dir, to_version)
        with zipfile.ZipFile(payload_zip) as zf:
            infos = [i for i in zf.infolist() if not i.is_dir()]
            top = _payload_top([i.filename for i in infos])
            need = sum(i.file_size for i in infos)
            free = shutil.disk_usage(install_dir).free
            if free < need + 64 * 1024 * 1024:
                msg = (f"not enough disk space: {need // 1048576} MB to stage, "
                       f"{free // 1048576} MB free")
                update_log.log("FAILED", to_version, msg + " - nothing was changed")
                return False, msg

            # 2. STAGE — every byte read and CRC-checked before anything moves
            staging = ud / "new"
            _rmtree(staging)
            staging.mkdir(parents=True)
            _write_json(ud / "journal.json", {"state": "staging", "top": top,
                                              "from_version": from_version,
                                              "to_version": to_version})
            for n, info in enumerate(infos, 1):
                zf.extract(info, staging)
                if n % 25 == 0 or n == len(infos):
                    progress(0.5 * n / len(infos), f"Unpacking {Path(info.filename).name[:40]}")
    except InterruptedRollbackIncomplete as e:
        # Not "nothing was changed", and never `_rmtree(ud)`: `.update\old`
        # and the journal are the only way back for the files still out
        # (bug R2, reviver round 1). recover_interrupted logged it; the next
        # run tries again.
        return False, str(e)
    except Exception as e:      # BadZipFile (CRC), zlib.error, OSError, a bad layout
        # nothing installed has been touched yet
        why = too_long(ud / "new", [i.filename for i in infos]) or f"{type(e).__name__}: {e}"
        update_log.log("FAILED", to_version, f"staging failed, nothing was changed: {why}")
        _rmtree(ud)
        return False, f"could not unpack the update: {why}"
    new_root = staging / top
    new_files = _files_under(new_root)
    update_log.log("STAGED", to_version, f"{len(new_files)} files, {need} bytes in {staging}")

    # 3. SWAP
    target, old = install_dir / top, ud / "old" / top
    old_files = _files_under(target)
    manifest = _read_json(install_dir / MANIFEST)
    shipped_before = set(manifest.get("files") or []) if manifest and manifest.get("top") == top else None
    if shipped_before is None:
        prune = old_files - new_files          # bridge: no record yet, the whole old tree was ours
    else:
        prune = (old_files & shipped_before) - new_files
    not_ours = sorted(old_files - new_files - prune)
    journal = {"state": "swapping", "top": top, "from_version": from_version,
               "to_version": to_version, "old_files": sorted(old_files)}
    try:
        _write_json(ud / "journal.json", journal)
        deadline = time.monotonic() + LOCK_RETRY_SECONDS
        order = sorted(new_files)
        for n, rel in enumerate(order, 1):
            src, dst, keep = new_root / rel, target / rel, old / rel
            if rel in old_files:
                keep.parent.mkdir(parents=True, exist_ok=True)
                if rel.lower().endswith(".exe"):
                    shutil.copy2(dst, keep)
                else:
                    _retry(lambda d=dst, k=keep: os.replace(d, k), deadline)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
            _retry(lambda s=src, d=dst: os.replace(s, d), deadline)
            if n % 25 == 0 or n == len(order):
                progress(0.5 + 0.45 * n / len(order), f"Installing {Path(rel).name[:40]}")
        for rel in sorted(prune):
            keep = old / rel
            keep.parent.mkdir(parents=True, exist_ok=True)
            _retry(lambda r=rel, k=keep: os.replace(target / r, k), deadline)
        _remove_empty_dirs(target, {p for r in new_files for p in _parents(r)})
        # 4. read it back: every new file in place, at its staged size
        missing = [r for r in new_files if not (target / r).is_file()]
        if missing:
            raise OSError(f"{len(missing)} file(s) missing after the swap, e.g. {missing[0]}")
    except Exception as e:
        ok, detail = rollback(install_dir, journal)
        update_log.log("FAILED", to_version,
                       f"swap failed ({type(e).__name__}: {e}); "
                       + ("rolled back: " if ok else "ROLLBACK INCOMPLETE: ") + detail)
        return False, f"the update could not be applied and was rolled back: {e}" if ok else \
            f"the update failed and could not be fully rolled back: {detail}"

    _rmtree(staging)
    try:
        _write_json(install_dir / MANIFEST, {"top": top, "version": to_version,
                                             "files": sorted(new_files)})
    except OSError:
        pass          # only the next update's pruning loses precision
    journal["state"] = "swapped"
    try:
        _write_json(ud / "journal.json", journal)
    except OSError:
        pass
    update_log.log("SWAPPED", to_version,
                   f"{len(new_files)} files in {target}; pruned {len(prune)}"
                   + (f"; kept {len(not_ours)} file(s) the installer did not put there"
                      if not_ours else ""))
    progress(1.0, "Installed")
    return True, f"installed v{to_version}"


def _parents(rel: str) -> list[str]:
    parts = rel.split("/")[:-1]
    return ["/".join(parts[:i]) for i in range(1, len(parts) + 1)]


# ─── after the new build has started ───


def finish_after_start(running_version: str, install_dir: Path | None = None) -> str:
    """Called by the app a few seconds after it started: if the update that
    put this build here is done, the rollback copy is not needed any more."""
    if install_dir is None:
        if not getattr(sys, "frozen", False):
            return ""
        # <install dir>\HappyPhotoOrganizer\HappyPhotoOrganizer.exe
        install_dir = Path(sys.executable).resolve().parent.parent
    ud = install_dir / UPDATE_DIR
    if not ud.exists():
        return ""
    j = _read_json(ud / "journal.json") or {}
    if j.get("state") == "swapped" and str(j.get("to_version")) == running_version:
        n = len(_files_under(ud))
        _rmtree(ud)
        update_log.log("CLEANED", running_version, f"removed the rollback copy ({n} files) in {ud}")
        return "cleaned"
    if j.get("state") == "swapping":
        return ""      # an interrupted swap: the next installer run rolls it back
    if not j:
        _rmtree(ud)
        return "cleared"
    return ""
