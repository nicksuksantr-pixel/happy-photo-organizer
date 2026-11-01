# Happy Photo Organizer — sorts ship-maintenance photos into dated, AI-named job folders

> **Stack:** Python 3.13 + CustomTkinter (Windows desktop), Gemini through `google-genai` · **Version: v1.069**
> **Path:** `C:\Users\NickSuksanTr\Documents\Projects\Happy-Photo-Organizer\`

## What it does

Nick drops a day's photos from a job on the ship. The app does the rest:
- it dates them;
- it shrinks them to email size (aiming for 10–25 KB);
- it puts each shooting day in its own folder;
- Gemini names each folder's job from a few sample photos, matched against the job catalog.

Nick checks the names in Step 3, and the app files everything as `DD-MM-YY <Job>/DD-MM-YY <Job>_001.jpg`. Jobs photographed on the phone (JobShot) arrive over Wi-Fi and file themselves. The app updates itself from GitHub Releases.

## Run / build

```powershell
# run from source
pip install -r requirements.txt
python main.py

# tests (no key, no network)
python tests/test_core.py

# build: also needs pyinstaller 6.20.0 and pywin32 (for .lnk shortcuts), and the free key in
# %USERPROFILE%\.embed-keys\Happy-Photo-Organizer.json (HPO_ALLOW_NO_KEY=1 builds without it)
pip install pyinstaller==6.20.0 pywin32
python tools/gen_codemap.py                       # regenerate docs/CODEMAP.md layer B (#15)
pyinstaller HappyPhotoOrganizer.spec --noconfirm --clean   # the app -> dist/HappyPhotoOrganizer/
python installer/build_installer.py              # the setup -> dist/HappyPhotoOrganizerSetup.exe
```

**Release, in this order** (needs `node` and a signed-in `gh`):
1. Bump `VERSION`, and set this README's Version line to match.
2. Regenerate the CODEMAP, then build (both build commands above).
3. Run the update drills (`drills/README.md`, #28).
4. Write the records, then commit and push.
5. Publish: `python tools/publish_release.py --previous <version users are on> --notes @<notes file>`.

The script refuses at each gate: an uncommitted tree, a bundle or build older than the source, a README Version line
that is not `VERSION`, a stale CODEMAP, or no passing drill receipt for these exact bytes.

## Features (one line each; files in `docs/CODEMAP.md`)

- **Capture date** from EXIF, then the file name, then the file time.
- **Resize** every photo towards 10–25 KB, with a JPEG integrity check; photos that stay over are counted and reported.
- **One shooting day = one folder.** A burst that crosses midnight stays with the day it started; the next day's
  later photos get their own folder.
- **AI job names** (Gemini Vision, 1–3 sample photos per folder), fuzzy-matched to the job catalog.
  - Non-work photos (screenshots, people, food) are flagged instead of being given a job name.
- **Step 3 review:**
  - edit any name (the EN button translates a Thai name);
  - delete a folder, or every non-work folder;
  - start a new batch.
- **Date allocation and rename:**
  - folders are moved into the destination's month with unique day numbers;
  - photos are named after their folder;
  - the destination folder is remembered.
- **Built-in free Gemini key, and the only key.**
  - The free limits (15 a minute, 500 a day) always apply, whatever tier was saved.
  - When AI is down, one line says why, and the run goes on without it.
  - A used-up day names the local time AI is back.
- **AI Health:** usage bars, 7-day history, recent calls, the quota and a pre-flight estimate.
- **JobShot:**
  - a phone pairs by QR;
  - jobs sent over Wi-Fi are received, checked, and filed with their report draft;
  - a resend never overwrites.
- **Self-update:**
  - only the published bytes run (the GitHub digest is checked twice);
  - the update waits while the app is busy;
  - the folder swap has a way back;
  - every step is written to `%USERPROFILE%\.happy-photo-organizer\logs\update.log`.
- **Tray icon, single instance, dark Windows title bar,** and the window remembers its size and place.
- **Installer:**
  - a single-page setup with shortcuts and an uninstaller in Add/Remove Programs;
  - it merges the job catalog instead of overwriting it.

## Doc map: what you want, where to open

| You want | Open |
|---|---|
| **Where to change the code** | `docs/CODEMAP.md` (open it before every edit) |
| Version history | `V-Log.md` (one line per version) · `CHANGELOG.md` (detail) |
| What each version's work was | `log/` (v1.057 on; older logs were rotated out of the repo under the quota rule, #6/#7, and are kept on the dev PC only) |
| Bugs found and how they were fixed | `bug/` (v1.055 on; older ones were rotated out the same way and are not in the repo) |
| Session history | `chat_log/` (newest file) |
| Workflow snapshot, risks, house rules | `memory/MEMORY.md` · `memory/nick-workflow.md` |
| How to release | "Release, in this order" above · `tools/publish_release.py` · `drills/README.md` (`RELEASE.md` = one-time setup and old notes) |
| Update drills before a release (#28) | `drills/README.md` · `memory/UPDATE_DRILL.md` |
| The free-tier limits the app enforces | `core/rate_limiter.py` `TIER_PRESETS` (`GEMINI_LIMITS.md` is older notes and still names 3.1) |
| Work parked for later | `docs/PARKED.md` |
| The old project summary (history, frozen at v1.057) | `PROJECT_SUMMARY.md` |

---
_Update this README when a feature is added or the version moves. `tools/publish_release.py` refuses a release whose Version line is not the `VERSION` file's, or whose CODEMAP is stale (#15)._
