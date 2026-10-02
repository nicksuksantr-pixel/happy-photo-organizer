"""publish_release.py — publish a release through gates that refuse.

WHY THIS EXISTS, in one paragraph, because the next person to touch it should
know what it is defending against rather than guess.

On 2026-10-02 the v1.061 upload failed with `HTTP 408` and the command still
reported success, because it was piped through `tail -1` and a pipe takes the
exit code of its LAST stage. The release was then published with **no asset**, so
`latest` pointed at a version the auto-updater could not download. It was caught
about a minute later by looking at the asset list — by eye, not by a gate. The
rule it broke is written down in this very repo, in `tools/pre-commit`: *a check
whose failure does not gate the next step is a report, not a guard.* Having the
rule, and having committed a reminder of it the same morning, did not help.

So: **it needs a tool, not more intention.** EMR built the equivalent on their
side the same evening and made the point that completes it — **a gate whose
failure path has never run is itself only a claim**, so every gate here is driven
to refuse in `tests/test_core.py` with a fake `run`, and the exact failure that
caused this file is a named test.

    python tools/publish_release.py            # publish the version in VERSION
    python tools/publish_release.py --check    # verify what is already published
    python tools/publish_release.py --dry-run  # run every local gate, touch nothing

Nick's standing authorisation covers publishing without asking. It does not cover
publishing something broken, which is the only thing this refuses.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REPO = "nicksuksantr-pixel/happy-photo-organizer"
LATEST_API = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET = "HappyPhotoOrganizerSetup.exe"
INSTALLER = ROOT / "dist" / ASSET
BUNDLED_VERSION = ROOT / "dist" / "HappyPhotoOrganizer" / "_internal" / "VERSION"


class Refused(Exception):
    """A gate said no. Nothing after it runs."""


def run(args: list[str], *, timeout: int = 900) -> str:
    """Run a command and return its stdout. **Never pipes, and never swallows.**

    This is the whole point of the file. `subprocess.run` with a captured pipe
    and an explicit returncode check is the shape; `cmd | tail` is the shape
    that published a release with no asset.
    """
    proc = subprocess.run(args, capture_output=True, timeout=timeout)
    out = proc.stdout.decode("utf-8", "replace")
    err = proc.stderr.decode("utf-8", "replace")
    if proc.returncode != 0:
        raise Refused(
            f"{' '.join(args[:3])}… exited {proc.returncode}: "
            f"{(err or out).strip()[:400]}")
    return out


# ─── local gates: everything that can be known before anything is published ───


def gate_tree_is_clean(*, runner=run) -> None:
    if runner(["git", "status", "--porcelain"]).strip():
        raise Refused("the working tree has uncommitted changes — commit first, "
                      "or the tag will not describe what was built")
    runner(["git", "fetch", "--quiet"])
    ahead_behind = runner(["git", "rev-list", "--left-right", "--count",
                           "HEAD...@{upstream}"]).split()
    if len(ahead_behind) == 2 and ahead_behind != ["0", "0"]:
        raise Refused(f"local and origin disagree (ahead {ahead_behind[0]}, "
                      f"behind {ahead_behind[1]}) — push or pull first")


def gate_version_agrees(version: str, *, bundled: Path = BUNDLED_VERSION) -> None:
    """VERSION, and the version INSIDE the thing that was built, must match.

    This is the gate that would have caught v1.061 a second way: a code fix
    landed after the build, so the binary waiting to upload was already behind
    the source it claimed to be.
    """
    try:
        inside = bundled.read_text(encoding="utf-8-sig").strip()
    except OSError as e:
        raise Refused(f"cannot read the built bundle's VERSION ({e}) — build first")
    if inside != version:
        raise Refused(f"VERSION says {version!r} but the built bundle says "
                      f"{inside!r} — rebuild, do not publish the old one")


def gate_bundle_is_not_stale(*, installer: Path = INSTALLER,
                             bundled: Path = BUNDLED_VERSION) -> None:
    """The installer must be newer than every tracked source file.

    v1.061's binary was built, then a fix was committed, then the upload was
    retried — so the bytes on their way to GitHub predated the commit they were
    supposed to carry. Nothing noticed, because nothing was looking.
    """
    if not installer.is_file():
        raise Refused(f"{installer} is not there — build first")
    built = installer.stat().st_mtime
    newest, which = 0.0, ""
    for pattern in ("*.py", "core/*.py", "ui/*.py", "ui/dialogs/*.py",
                    "installer/*.py", "VERSION", "*.spec"):
        for f in ROOT.glob(pattern):
            m = f.stat().st_mtime
            if m > newest:
                newest, which = m, f.name
    if newest > built:
        raise Refused(f"{which} is newer than the installer — the build is "
                      f"stale, rebuild before publishing")
    if bundled.is_file() and bundled.stat().st_mtime > built:
        raise Refused("the frozen bundle is newer than the installer — the "
                      "installer was not rebuilt from it")


def gate_asset_is_named_correctly(*, installer: Path = INSTALLER) -> None:
    """The auto-updater matches on this exact name (updater.py:33). A renamed
    asset is a release nobody can install, and it looks fine on the page."""
    if installer.name != ASSET:
        raise Refused(f"the artifact is {installer.name!r}, and the updater "
                      f"only ever looks for {ASSET!r}")


# ─── the gate the whole file exists for ───


def gate_published(version: str, *, expect_bytes: int, fetch=None) -> dict:
    """After publishing: is it REALLY there, and is it the right bytes?

    Refuses: still a draft · no asset · more than one · an asset still
    uploading · a size that does not match what was built locally · a `latest`
    that names a different tag.
    """
    fetch = fetch or _fetch_latest
    body = fetch()
    tag = body.get("tag_name")
    if tag != f"v{version}":
        raise Refused(f"`latest` names {tag!r}, not v{version} — "
                      f"**revert it to a draft now** so `latest` falls back to "
                      f"the previous working release")
    if body.get("draft"):
        raise Refused("it is still a draft")
    assets = [a for a in (body.get("assets") or []) if a.get("name") == ASSET]
    if not assets:
        raise Refused(
            f"PUBLISHED WITH NO {ASSET} — the updater cannot download this. "
            f"**Revert it to a draft now** so `latest` falls back to the "
            f"previous working release, then delete the tag so the history "
            f"does not claim a version that never existed.")
    if len(assets) > 1:
        raise Refused(f"{len(assets)} assets named {ASSET}")
    a = assets[0]
    if a.get("state") != "uploaded":
        raise Refused(f"the asset state is {a.get('state')!r}, not 'uploaded' — "
                      f"it has not finished")
    if int(a.get("size") or 0) != int(expect_bytes):
        raise Refused(f"the published asset is {a.get('size')} bytes and the "
                      f"local build is {expect_bytes} — not the same file")
    return body


def gate_the_app_would_offer_it(version: str, previous: str) -> None:
    """Ask the APP, not the API. The updater is the only consumer that matters,
    and it is the one that silently found nothing on 2026-10-02."""
    from core import updater
    info = updater.check_for_update(previous, timeout=15.0)
    if info is None:
        raise Refused(f"the app's own updater offers nothing to a v{previous} "
                      f"user — this release is invisible to the people on it")
    if getattr(info, "version", None) != version:
        raise Refused(f"the updater offers {getattr(info, 'version', None)!r} "
                      f"to a v{previous} user, not {version!r}")
    if not getattr(info, "download_url", ""):
        raise Refused("the updater found the release but no download URL")
    current = updater.check_for_update(version, timeout=15.0)
    if current is not None:
        raise Refused(f"a v{version} user is offered {current.version!r} — "
                      f"the version comparison is wrong")


def _fetch_latest() -> dict:
    req = urllib.request.Request(LATEST_API, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


# ─── the flow ───


def local_gates(version: str) -> int:
    gate_tree_is_clean()
    gate_version_agrees(version)
    gate_bundle_is_not_stale()
    gate_asset_is_named_correctly()
    size = INSTALLER.stat().st_size
    print(f"  local gates passed · v{version} · {size:,} bytes")
    return size


def publish(version: str, previous: str, notes: str) -> None:
    size = local_gates(version)
    tag = f"v{version}"

    existing = run(["git", "tag", "-l", tag]).strip()
    if not existing:
        run(["git", "tag", tag])
        run(["git", "push", "origin", tag])

    # draft FIRST, upload, verify, and only then publish. The order is the
    # recovery: nothing is `latest` until the bytes are known to be there.
    run(["gh", "release", "create", tag, "--draft", "--title",
         f"v{version}", "--notes", notes])
    print("  draft created; uploading…")
    run(["gh", "release", "upload", tag, str(INSTALLER), "--clobber"],
        timeout=3600)

    raw = run(["gh", "release", "view", tag, "--json", "assets,isDraft"])
    view = json.loads(raw)
    got = [a for a in view.get("assets") or [] if a.get("name") == ASSET]
    if not got or int(got[0].get("size") or 0) != size:
        raise Refused(
            f"the upload did not land ({len(got)} asset(s)) — the release is "
            f"still a DRAFT, which is the safe state. Retry the upload; do not "
            f"publish.")
    print(f"  asset verified on the draft: {got[0]['size']:,} bytes")

    run(["gh", "release", "edit", tag, "--draft=false"])
    gate_published(version, expect_bytes=size)
    gate_the_app_would_offer_it(version, previous)
    print(f"  PUBLISHED and verified from outside · v{version}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", metavar="VERSION", help="verify a published version")
    ap.add_argument("--dry-run", action="store_true", help="local gates only")
    ap.add_argument("--previous", default="", help="the version users are on")
    ap.add_argument("--notes", default="", help="release notes (or a @file)")
    a = ap.parse_args()

    version = (ROOT / "VERSION").read_text(encoding="utf-8-sig").strip()
    try:
        if a.check:
            size = INSTALLER.stat().st_size if INSTALLER.is_file() else 0
            body = gate_published(a.check, expect_bytes=size) if size else None
            if body:
                print(f"  v{a.check} published, asset matches the local build")
            if a.previous:
                gate_the_app_would_offer_it(a.check, a.previous)
                print(f"  and the app offers it to a v{a.previous} user")
            return 0
        if a.dry_run:
            local_gates(version)
            return 0
        notes = a.notes
        if notes.startswith("@"):
            notes = Path(notes[1:]).read_text(encoding="utf-8")
        if not notes.strip():
            raise Refused("--notes is required; a release with no notes is a "
                          "release nobody can read later")
        if not a.previous:
            raise Refused("--previous is required: the gate that matters asks "
                          "whether a user on the PREVIOUS version is offered "
                          "this one")
        publish(version, a.previous, notes)
        return 0
    except Refused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
