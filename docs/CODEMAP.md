# CODEMAP — Happy Photo Organizer

> **Open this before every code change**, so you go straight to the right file instead of reading the project.
> Layer A is written by hand. Layer B is generated: never edit it by hand.
> Regenerate layer B: `python tools/gen_codemap.py` · check it: `python tools/gen_codemap.py --check`
> `tools/publish_release.py` refuses a release while layer B is stale (rule #15).

## Layer A — where to change what (hand-written)

The batch has four phases:
- **Phases 1, 2 and 4** are in `core/processor.py`, and `main.py` runs them on worker threads.
- **Phase 3** is the user's review: Step 3 in `main.py` and `ui/job_row.py`.

| To change | File | Entry point |
|---|---|---|
| **The window**: layout and steps | `main.py` | `MainWindow._build_ui` / `_build_step1`…`_build_step3` |
| Keyboard shortcuts | `main.py` | bound in `MainWindow.__init__`, handled in `_kbd_open` / `_kbd_run` / `_kbd_cancel` / `_kbd_check_update` |
| Step status colours, which buttons are live | `main.py` · `ui/step_card.py` | `MainWindow._refresh_step_states`, `_sync_commit_button`, `_reset_buttons` · `StepCard.set_status` |
| Drop / Start / Commit | `main.py` | `_on_drop` (adds sources; phone-job folders go to `_import_jobshot`) · Start button or `_kbd_run` → `_start_phase12` → `_phase12_worker` · Commit → `_start_phase4` → `_phase4_worker` → `_on_rename_done` |
| "Start a new batch", clearing a finished batch | `main.py` | `MainWindow._on_new_batch`, `_reset_batch` |
| The destination folder, and remembering it | `main.py` · `core/jobshot.py` | `MainWindow._set_dest` / `_restore_dest` · `get_dest_root`, `remember_dest_root` |
| The window's size and place, remembered | `main.py` | `MainWindow._restore_window_state`, `_save_window_state`, `_is_geometry_onscreen` |
| **Phase 1**: collect, resize, group | `core/processor.py` | `phase1_resize_and_group` |
| Which files count as photos (formats, HEIC) | `core/image_io.py` | `SUPPORTED_EXTS`, `is_supported_image`, `collect_images` |
| Capture date (EXIF → file name → file time) | `core/exif_reader.py` | `get_capture_date` |
| Resize: the algorithm | `core/resizer.py` | `resize_to_target` |
| Resize: the 10/25 KB numbers actually used | `main.py` · `core/processor.py` · `core/jobshot.py` | `MainWindow.__init__` (`target_kb_min` / `target_kb_max`) · `phase1_resize_and_group` defaults · `import_job` / `import_batch` defaults |
| One shooting day = one folder (the midnight bridge) | `core/grouper.py` · `core/processor.py` | `group_by_session` · the gap actually used: `phase1_resize_and_group(time_gap_minutes=…)` |
| **Phase 2**: the AI pass over every folder | `core/processor.py` | `phase2_ai_analyze` |
| The Gemini prompt | `core/analyzer.py` | `ANALYZER_SYSTEM_PROMPT`, `_build_user_prompt`, the group suffix in `analyze_group` (`analyze_image` is used only by `scripts/smoke_test.py`) |
| The reply parsing, retries | `core/analyzer.py` | `_parse_json_response`, `_generate_with_retry`, `_is_transient_error` |
| Why AI is down: withdrawn / today's quota / busy / wrong model | `core/analyzer.py` · `core/processor.py` | `ai_down_fields` · `ai_down_line`, `quota_back_at` |
| … no internet | `core/processor.py` | `_OFFLINE` and the end-of-run block of `phase2_ai_analyze` |
| Translating a Thai job name (the EN button), a second Gemini prompt | `ui/job_row.py` | `JobRow._translate_to_english` |
| Job catalog: names, fuzzy match | `core/catalog.py` | `JobCatalog.find_fuzzy`, `JobCatalog.find` |
| Job catalog: when a typed name is learned, and saved | `main.py` · `core/catalog.py` · `core/processor.py` | `MainWindow._refresh_summary` · `JobCatalog.add`, `record_usage` · saved in `phase4_rename_folders` and `MainWindow.destroy` |
| Date allocation (destination's month, unique days) | `core/processor.py` | `detect_target_month`, `scan_used_days`, `assign_unique_dates` |
| Folder and photo names (`DD-MM-YY <Job>_001.jpg`) | `core/processor.py` · `core/exif_reader.py` | `JobAssignment.folder_name`, `photo_prefix`, `rename_photos_for_folder`, `sanitize_filename` · `format_folder_date` |
| **Phase 4**: the rename / merge into the destination | `core/processor.py` | `phase4_rename_folders` |
| **Step 3 rows**: thumbnails, editing a name | `ui/job_row.py` · `main.py` | `JobRow` · `MainWindow._render_plan` |
| Delete a folder, or all non-work folders | `main.py` · `core/processor.py` | `MainWindow._delete_assignment`, `_delete_flagged` (confirm) · `discard_assignment` (decides what may be deleted) |
| The Gemini key (built in, the only key) | `core/auth.py` · `core/keymask.py` | `get_api_key`, `using_bundled_key`, `create_client` · `read_bundled_key`, `fingerprint` |
| The model: default, choice, saving | `core/auth.py` · `core/rate_limiter.py` · `ui/dialogs/settings.py` · `ui/dialogs/ai_health.py` | `DEFAULT_MODEL`, `get_model` · `DEFAULT_TIER`, `TIER_PRESETS` · the model list in `SettingsDialog.__init__`, `SettingsDialog._save` · `AIHealthDialog._apply_tier` |
| Free-tier limits, RPM/RPD throttle, tier presets, the built-in key's ceiling | `core/rate_limiter.py` | `TIER_PRESETS`, `RateLimiter.acquire`, `update_tier_from_config` |
| The pre-flight estimate before Start | `core/rate_limiter.py` · `main.py` · `ui/dialogs/ai_health.py` | `RateLimiter.estimate_eta` · the pre-flight block in `MainWindow._start_phase12` · `AIHealthDialog._update_preflight` |
| Usage counts, the 7-day history | `core/usage_log.py` | `UsageLog.record_call`, `UsageLog.snapshot` |
| The Pacific day (two separate computations) | `core/usage_log.py` · `core/processor.py` | `PT_TZ`, `_now_pt`, `_seconds_until_pt_midnight` · `quota_back_at` (its own US daylight-time rule): change both together |
| The header badge (model, live RPM) | `main.py` | `MainWindow._update_tier_badge`, `_poll_quota_badge` |
| The AI Health dialog | `ui/dialogs/ai_health.py` | `AIHealthDialog` |
| The Settings dialog (model, UI scale, auto-update) | `ui/dialogs/settings.py` | `SettingsDialog._save` |
| Saved settings (`auth.json`), atomic writes | `core/auth.py` | `load_config`, `update_config`, `atomic_write_json` |
| **JobShot**: pairing a phone (QR, token, ship) | `ui/dialogs/pairing.py` · `core/jobshot_receive.py` | `PairingDialog` · `qr_payload`, `get_token`, `verify_token` |
| JobShot: the LAN receiver (HTTP routes) | `core/jobshot_server.py` | `JobShotReceiver.start`; routes in `_Handler.do_GET` / `do_POST` |
| JobShot: an upload made safe (zip checks, extraction) | `core/jobshot_receive.py` | `receive_zip`, `safe_extract`, `replace_sidecars` |
| JobShot: filing a job and its report draft | `core/jobshot.py` | `import_job`, `import_batch` |
| JobShot: "was this job filed?" and a job still landing | `core/jobshot_index.py` | `lookup`, `record`, `begin_filing` / `wait_while_filing` |
| JobShot from the PC side (button, Wi-Fi arrivals) | `main.py` | `MainWindow._import_jobshot`, `_on_wifi_job`, `_start_receiver_if_paired` |
| **Self-update**: when to check, finding a release | `core/update_worker.py` · `core/updater.py` | `UpdateWorker.tick` (schedules), `_poll_github` · `check_for_update` |
| Self-update: download and verify the digest | `core/updater.py` · `core/update_worker.py` | `download_installer` (size), `sha256_of` · `UpdateWorker._begin_download` (hash = digest, else refused), `_still_verified` (re-hash before running) |
| Self-update: when to install, waiting while busy | `core/update_worker.py` · `main.py` | `UpdateWorker._on_ready`, `_install_now`, `busy_reason`, `_schedule_idle_retry`, `resume_deferred` · `MainWindow.busy_reason` (what counts as busy), `on_before_install` |
| The update button (label, click) | `main.py` · `core/update_worker.py` | `MainWindow._on_update_button`, `_poll_update_button`, `_UPDATE_COLOURS` · `UpdateWorker.describe`, `install_pending_now` (the manual Install path) |
| Self-update: the folder swap and its way back | `core/install_swap.py` | `swap_in`, `rollback`, `recover_interrupted`, `finish_after_start` |
| The update log (`%USERPROFILE%\.happy-photo-organizer\logs\update.log`) and failed-attempt record | `core/update_log.py` | `log`, `started`, `begin_attempt`, `settle_attempt` |
| Drill-only hooks (feed, busy marker, key check) | `core/updater.py` · `core/key_check.py` | `drill_mode`, `feed_url`, `take_drill_busy_marker` · `run` |
| Tray icon, closing to tray | `core/tray.py` · `main.py` | `HappyTray` · `MainWindow._start_tray`, `_on_main_close` |
| One instance per user | `core/single_instance.py` | `ensure_single_instance` |
| Colours, title bar, copy/paste across keyboard layouts | `ui/theme.py` · `ui/win_chrome.py` · `ui/paste_helper.py` | the installer has its own copies: `installer/installer.py` `COLOR_*`, `enable_paste` |
| The version shown everywhere | `VERSION` · `core/version.py` | `read_version` |
| **The installer**: install, upgrade, catalog merge, uninstaller | `installer/installer.py` | `Installer.install`, `Installer._merge_catalog`, `_run_silent_upgrade`, `SetupWindow` |
| Building: the app, then the setup | `HappyPhotoOrganizer.spec` (the app) · `installer/HappyPhotoOrganizerSetup.spec` (the setup) · `installer/build_installer.py` | `main` (`zip_payload` → `build_installer`) |
| **Releasing** and its gates | `tools/publish_release.py` | `local_gates`, `publish` |
| The release lock (drill receipts, #28; README and CODEMAP present, #15) | `tools/release-gate.mjs` | house file: never edit here |
| Keeping the key out of git (commit hooks) | `tools/key_guard.py` · `tools/pre-commit` · `tools/commit-msg` | `main` |
| This map's layer B | `tools/gen_codemap.py` | `build_auto`, `SECTIONS` |
| The update drill adapter (#28) | `drills/hpo.ps1` · `drills/drill.json` | see `drills/README.md`; `drills/kit/` is the house kit (adopt by copy only) |
| Tests | `tests/test_core.py` | one file; run `python tests/test_core.py` |

## Layer B — modules and their public names (generated; do not edit by hand)
<!-- CODEMAP:AUTO:START -->
### main.py — the window
- `main.py` — Happy Photo Organizer — main entry point.
    • `class MainWindow` — Main app window: drop photos, group and resize them, name each job with AI, then file them.
        ↳ is_batch_running, log, on_before_install, busy_reason, destroy
    • `main()` — Entry point: enforce a single instance, sweep stale leftovers, then run the main window.

### core/ — logic, no UI
- `core/analyzer.py` — analyzer.py — Gemini Vision wrapper
    • `ai_down_fields(text)` — {"ai_down": <cause>, "ai_down_permanent": bool} when `text` (an error)
    • `analyze_image(image_path, catalog_names, client, model, cancel_event)` — ส่งรูป 1 ใบให้ Gemini พิจารณา → คืน dict ตาม schema
    • `analyze_group(image_paths, catalog_names, client, model, sample_size, cancel_event)` — วิเคราะห์กลุ่มรูป (เช่นรูปหลายใบของงานเดียวกัน) — ส่ง sample ไม่กี่ใบไป Gemini เพื่อประหยัด quota
- `core/auth.py` — auth.py — Gemini API key + model management
    • `atomic_write_json(path, data, lock_perms)` — Write `data` to `path` atomically. Returns success.
    • `cleanup_stale_quarantines(max_age_days)` — Round-6 BUG-L10 (Cos review 2026-05-24): sweep auth.corrupt-<ts>.json
    • `load_config()` — Load config — คืน dict ว่างถ้าไม่มีไฟล์
    • `update_config(updates)` — Merge `updates` into current config and persist. Returns success.
    • `get_bundled_key()` — The free key built into the app (Nick, 2026-10-31), or None.
    • `get_api_key()` — The key to use: the built-in free key, and nothing else (house standard
    • `using_bundled_key()` — True when the app has its built-in free key (shared by every install,
    • `get_model()` — The Gemini model saved in auth.json, or DEFAULT_MODEL when it is missing or blank.
    • `create_client(api_key)` — สร้าง Gemini client — the built-in key, or one passed in (key_check).
    • `test_connection(client)` — ลอง list models เพื่อทดสอบว่า key ใช้ได้
    • `list_vision_models(client)` — List Gemini models ที่ใช้ดูรูปได้ (vision / image understanding)
- `core/catalog.py` — catalog.py — manage job_catalog.json
    • `class JobCatalog` — โหลด/อัพเดท job catalog — thread-safe.
        ↳ load, save, names, find, find_fuzzy, add, record_usage
- `core/exif_reader.py` — exif_reader.py — ดึงวันที่ถ่ายจากรูป
    • `read_from_exif(path)` — อ่าน EXIF DateTimeOriginal จากไฟล์รูป
    • `read_from_filename(path)` — พยายามดึงวันที่จากชื่อไฟล์
    • `read_from_mtime(path)` — The file's last-modified time as a local datetime, or None if it cannot be read.
    • `get_capture_date(path)` — คืน (datetime, source) — source = 'exif' | 'filename' | 'mtime'
    • `format_folder_date(dt)` — Format วันที่สำหรับชื่อโฟลเดอร์: DD-MM-YY
    • `format_file_timestamp(dt)` — Format สำหรับ rename ไฟล์ Happy_Ena_YYYY-MM-DD_HH-MM-SS
- `core/grouper.py` — grouper.py — จับกลุ่มรูปก่อนส่งให้ AI วิเคราะห์
    • `class PhotoGroup` — กลุ่มของรูปที่น่าจะเป็นงานเดียวกัน
        ↳ start_date, end_date, representative_date
    • `collect_images(folder, recursive)` — รวบรวมไฟล์รูปจากโฟลเดอร์ — ใช้ image_io เพื่อรองรับสกุลครบ
    • `group_by_session(images, time_gap_minutes)` — จับกลุ่มรูป: 1 วันที่ถ่าย = 1 กลุ่ม (= 1 โฟลเดอร์)
- `core/image_io.py` — image_io.py — รวม image format support
    • `is_supported_image(path)` — True when the file's extension is one of SUPPORTED_EXTS (case-insensitive).
    • `get_mime_type(path)` — คืน MIME type จากนามสกุล — ใช้ส่งให้ Gemini
    • `open_image(path)` — เปิดรูปแบบไหนก็ได้ — return Pillow Image
    • `collect_images(folder, recursive)` — รวมไฟล์รูปทุกสกุลที่รองรับจากโฟลเดอร์
    • `format_summary()` — สำหรับแสดงใน UI
- `core/install_swap.py` — install_swap.py — replace the installed app in place, with a way back (v1.066).
    • `app_running()` — True while any process holds the app's single-instance mutex.
    • `app_window_open()` — True if a visible Tk window titled like the app exists. Used only after
    • `wait_for_app_exit(timeout, poll)` — Wait for the app to let go of its mutex. True once it has.
    • `process_info(pid)` — (full exe path, creation time as a FILETIME number) of a live process,
    • `parent_pid(pid)` — The pid that started `pid`, from a process snapshot.
    • `handover_parent(app_exe, max_hops)` — The process that started this upgrade, if it is the app being replaced:
    • `end_handover_parent(parent, timeout)` — End `parent` (from `handover_parent`) and wait for it. Only while the
    • `too_long(root, names)` — Why files named `names` cannot be written under `root`, or "": past
    • `rollback(install_dir, journal)` — Put the old tree back from `.update\old\`, per the journal. Safe to run
    • `class InterruptedRollbackIncomplete` — An earlier interrupted swap could not be fully put back on this run.
    • `recover_interrupted(install_dir, to_version)` — Before a new swap: finish whatever an earlier run left in `.update\`.
    • `swap_in(payload_zip, install_dir, from_version, to_version, progress_cb)` — Install `payload_zip` into `install_dir`, replacing what is there in
    • `finish_after_start(running_version, install_dir)` — Called by the app a few seconds after it started: if the update that
- `core/jobshot.py` — jobshot.py — file a job that was photographed on the phone (JobShot).
    • `class ImportResult` — The outcome of filing one arrived JobShot folder: where it went, what was filed, any errors.
    • `is_complete(job_folder)` — True once the phone has written the manifest — i.e. the transfer is done.
    • `read_manifest(job_folder)` — Return (manifest, error). Never raises — a half-written or hand-edited
    • `get_dest_root(ship)` — The photo folder Nick picked on this vessel's PC, if one is remembered.
    • `remember_dest_root(ship, dest_root)` — Remember it per vessel, so an arriving job files itself into the right
    • `job_key(job_name, work_date)` — What makes two arrivals the same job: its name and the day it was done.
    • `unreadable_manifests(dest_root)` — Folders holding a `job*.json` this PC cannot parse.
    • `find_manifest_path(folder, job_id)` — The path of the manifest in `folder` that belongs to `job_id`.
    • `find_filed_job(dest_root, job_name, work_date)` — The folder this job already lives in, if it has been filed before.
    • `split_arrivals(paths)` — Sort dropped/browsed paths into (jobs, still-arriving, everything else).
    • `import_job(job_folder, dest_root, target_kb_min, target_kb_max, max_dim, catalog, progress_cb)` — Take one arrived JobShot folder and file it — resize, date rule, commit,
    • `import_batch(job_folders, dest_root, target_kb_min, target_kb_max, max_dim, catalog, progress_cb)` — File several arrivals at once, grouping the ones that are the same job
- `core/jobshot_index.py` — jobshot_index.py — "have you already filed this job?", answerable later.
    • `valid_job_id(job_id)` — True when job_id is 1-128 characters of letters, digits, dot, underscore or hyphen.
    • `begin_filing(job_ids)` — Register these jobs as being filed. Returns the ids actually registered
    • `end_filing(job_ids)` — Release what `begin_filing` registered - on success AND on failure.
    • `is_filing(job_id)` — True while this job is registered as being filed (between begin_filing and end_filing).
    • `begin_receiving()` — Count one more phone request as being received - pair it with `end_receiving`.
    • `end_receiving()` — Release one request counted by `begin_receiving`; the count never drops below zero.
    • `any_filing()` — Anything arriving from a phone or being filed right now. The updater
    • `wait_while_filing(job_id, timeout)` — Wait until nothing is filing this job. True once it is not (or never
    • `record(job_id, folder, photos, extras, filed_at)` — Write the receipt. Called for every job filed, by every route.
    • `lookup(job_id, dest_root)` — What this PC did with that job, or None if it has no record of it.
    • `forget_all()` — Only for tests and for a deliberate reset — never called on a failure.
- `core/jobshot_receive.py` — jobshot_receive.py — take a job zip that arrived over the LAN and make it safe.
    • `named_job_ids(raw, claimed)` — Read `X-JobShot-Job-Ids`. Returns (ids, why it was ignored).
    • `class ReceiveResult` — The outcome of one upload from the phone: the jobs filed, skipped and any errors or warnings.
        ↳ to_reply
    • `class SidecarResult` — The answer to a sidecar replacement. `status` is the HTTP code the server
        ↳ to_reply
    • `replace_sidecars(job_id, files, dest_root)` — Replace one or more sidecars on a job this PC has already filed.
    • `get_token(create)` — The token the QR carries and every upload must present.
    • `verify_token(presented)` — Constant-time compare against the paired token. No token on the PC means
    • `local_ip()` — The address the phone should dial. Asks the OS which interface it would
    • `qr_payload(ship, port, host)` — What the pairing QR encodes.
    • `safe_extract(data, quarantine)` — Unpack a received zip into `quarantine`. Returns (ok, error, warnings).
    • `io_bytes(data)` — Small helper so the zip is read from memory — a received upload is never
    • `receive_zip(data, dest_root, quarantine_root, expected_ship, catalog, progress_cb)` — The whole receiving side, minus the socket: validate, unpack, file.
    • `load_reply(raw)` — Parse a reply (for the tests and for anyone debugging the phone side).
- `core/jobshot_server.py` — jobshot_server.py — the socket half of the LAN receiver.
    • `class JobShotReceiver` — Owns the listening socket. Start it when HPO opens, stop it on exit.
        ↳ start, ensure_started, stop, running, address
- `core/key_check.py` — key_check.py — one real Gemini call with the built-in key, for the update drill.
    • `result_path()` — Where `run` writes the key-check result by default: logs/embedded-key-check.json.
    • `run(out_path, client_factory)` — Make the call, write the result, return it. Never raises, never
- `core/keymask.py` — keymask.py — the built-in Gemini key: where it is kept, how it is recognised.
    • `embed_key_file()` — The embed-key file outside the repo: ~/.embed-keys/Happy-Photo-Organizer.json.
    • `read_embed_key(path)` — The key from the embed-key file, or None — never raises.
    • `read_bundled_key(path)` — The key from the bundled `data/gemini.key`, or None — never raises.
    • `fingerprint(key)` — sha256 of the key — what a receipt or the house registry carries
    • `redact(text)` — `text` with anything shaped like a key replaced — for messages and logs.
- `core/processor.py` — processor.py — Engine ที่ orchestrate ทุก step
    • `sanitize_filename(s, max_len)` — Replace characters Windows forbids with spaces, collapse whitespace and cut to max_len.
    • `photo_prefix(folder_name, parent, tail_len)` — The `DD-MM-YY <Job>` part of a photo's name, trimmed so the finished
    • `rename_photos_for_folder(temp_folder, target, folder_name)` — Rename this run's photos — still inside the temp folder — to
    • `class JobAssignment` — งาน 1 งาน = โฟลเดอร์ output 1 โฟลเดอร์
        ↳ folder_name, needs_review, date_shifted
    • `class Plan` — One run's work: the job folder assignments under dest_root, with counts and any AI failure.
    • `class CommitResult` — What phase4_rename_folders did: folders renamed, rows skipped or already done, and errors.
    • `scan_used_days(dest_root)` — Scan dest_root → คืน set ของ 'day numbers' (1-31) ที่ปรากฏแล้ว
    • `detect_target_month(dest_root)` — หา (year, month) ที่ปรากฏมากที่สุดจากชื่อ folders ใน dest_root.
    • `assign_unique_dates(plan, used_days, target_year_month)` — ปรับ folder_date ของแต่ละ assignment.
    • `phase1_resize_and_group(sources, dest_root, target_kb_min, target_kb_max, max_dim, time_gap_minutes, progress_cb, cancel_event)` — 1. รวบรวมรูปจาก sources
    • `discard_assignment(plan, assignment)` — Drop one assignment from the plan and delete the working copy it owns.
    • `phase2_ai_analyze(plan, catalog, sample_size, max_workers, progress_cb, cancel_event)` — Phase 2: ส่ง 1-3 รูปต่อโฟลเดอร์ให้ Gemini วิเคราะห์ — parallel ผ่าน ThreadPoolExecutor
    • `ai_down_line(cause, now, local_tz)` — The one line telling the user why the AI cannot run, by cause; "day" says when it is back.
    • `quota_back_at(now, local_tz)` — The next midnight US Pacific after `now`, on `local_tz`'s clock (this
    • `phase4_rename_folders(plan, progress_cb, cancel_event, catalog)` — Rename temp folders ('YYYY-MM-DD__pending_NN') → final ('DD-MM-YY [ชื่องาน]')
- `core/rate_limiter.py` — rate_limiter.py — Thread-safe throttle + quota enforcement for Gemini calls
    • `class QuotaExceededError` — Raised เมื่อ daily quota ครบ
    • `class TierConfig` — One rate tier: its RPM/RPD/TPM limits, whether to throttle, and the model it implies.
        ↳ from_preset, custom, min_interval_sec
    • `class RateLimiter` — Thread-safe — รองรับ parallel workers ผ่าน ThreadPoolExecutor
        ↳ update_tier, check_quota, acquire, record, call, estimate_eta
    • `get_rate_limiter()` — The app-wide RateLimiter, created on first use with the default tier.
    • `update_tier_from_config(cfg)` — โหลด tier จาก auth.json config → return limiter ที่ตั้งค่าใหม่
- `core/resizer.py` — resizer.py — ย่อรูป target 10-25 KB
    • `resize_to_target(src_path, dst_path, target_kb_min, target_kb_max, max_dim)` — ย่อรูปลงให้ขนาดอยู่ระหว่าง target_kb_min ถึง target_kb_max
- `core/single_instance.py` — single_instance.py — Win32 named-mutex single-instance guard.
    • `ensure_single_instance()` — Returns True if this is the first instance (proceed to launch the app).
- `core/tray.py` — tray.py — System-tray wrapper around pystray.Icon.
    • `class HappyTray` — Wraps pystray.Icon with our app's menu (Show / Check update / Quit).
        ↳ start, stop
- `core/update_log.py` — update_log.py — the one file that says what an update did (UPDATE_DRILL §3.3).
    • `set_enabled(on)` — Off only for the drill's reference install (`--fresh-into`), which is
    • `log_path()` — The update log every stage appends to: ~/.happy-photo-organizer/logs/update.log.
    • `log(stage, version, detail)` — `<ISO> UPDATE <STAGE> <version> <detail>` — never raises.
    • `started(version, exe)` — `<ISO> STARTED <version> <exe path>` — on every start (§3.3).
    • `attempt_path()` — The record of the install in flight, update-attempt.json beside update.log.
    • `read_attempt()` — The recorded install attempt, or None when there is none or it is unreadable - never raises.
    • `clear_attempt()` — Delete the recorded install attempt, if any - never raises.
    • `begin_attempt(version)` — The app, at HANDOVER: `version` is about to be installed.
    • `note_attempt_failed(version, reason)` — The installer, when it gives up. False when no app wrote an attempt for
    • `settle_attempt(running_version)` — The app, at start. None when nothing was in flight, or when it came up
- `core/update_worker.py` — update_worker.py — Auto-update lifecycle owner.
    • `class UpdateWorker` — Owns auto-update state. One per app instance.
        ↳ in_progress, in_progress, start, cancel, tick, manual_check, describe, install_pending_now, retry_failed, busy_reason, resume_deferred
- `core/updater.py` — updater.py — Check GitHub Releases for newer version, download installer, relaunch
    • `class UpdateInfo` — A newer release that may be installed: its version, notes, installer URL, size and SHA-256.
    • `class UpdateCheckFailed` — GitHub could not be asked, or did not answer with a release.
    • `class UpdateRefused` — GitHub answered, and the answer is not something to install: a newer
    • `is_newer(current, latest)` — latest > current?  Pads shorter tuple with zeros.
    • `drill_mode()` — True when this run is an update drill, i.e. HAPPY_UPDATE_DRILL is set to "1".
    • `take_drill_busy_marker(data_dir)` — True once, when a drill asked this start to come up busy. Outside a
    • `feed_url()` — (latest-release URL, is_drill_feed). Read at call time, not import, so a
    • `check_for_update(current_version, timeout)` — Returns UpdateInfo if a newer release exists, None if GitHub ANSWERED
    • `sha256_of(path)` — Hex SHA-256 of a file, or "" if it cannot be read.
    • `download_installer(url, dest, progress_cb, cancel_event, chunk_size, max_attempts, attempt_timeout, expected_size)` — Download URL → dest with retry + HTTP Range resume.
    • `launch_installer_and_exit(installer_path, silent, version)` — Spawn installer (detached) then exit current process.
    • `cache_dir()` — The folder downloaded installers go to, ~/.happy-photo-organizer/updates, created if missing.
    • `cleanup_old_installers(keep)` — Empty the download cache, except `keep`.
- `core/usage_log.py` — usage_log.py — จัดการ usage tracking ของ Gemini API
    • `class UsageLog` — Thread-safe usage tracker — เก็บใน JSON file
        ↳ record_call, today_count, today_tokens, current_rpm, history_7d, recent_calls, seconds_until_reset, reset_today, snapshot
    • `get_usage_log()` — The app-wide UsageLog, created on first use.
- `core/version.py` — version.py — Single source of truth for APP_VERSION.
    • `read_version()` — The first non-empty VERSION file (bundle first, then project root), else "0.0.0".

### ui/ — widgets
- `ui/job_row.py` — job_row.py — One row in the Review & Edit pane.
    • `class JobRow` — One job folder's row in the Review & Edit pane: thumbnail, date, name box and AI confidence.
        ↳ mark_filed, refresh_catalog_values
- `ui/paste_helper.py` — paste_helper.py — Cross-keyboard-layout copy/cut/paste/select-all.
    • `enable_paste(widget)` — Wire Ctrl+V/C/X/A + right-click context menu on widget.
- `ui/step_card.py` — step_card.py — Numbered step card with circle indicator + title + body slot.
    • `class StepCard` — Numbered workflow step card with a status circle, title, status label and a `body` frame.
        ↳ set_status
- `ui/theme.py` — theme.py — Color palette + step status colors.
- `ui/win_chrome.py` — win_chrome.py — Windows title-bar chrome helpers.
    • `apply_dark_title_bar(window)` — Switch the OS title bar of `window` to dark mode (Win 10/11 only).
    • `register_default_icon(icon_path)` — Register `icon_path` (.ico) as the Tk-class-level default icon so
    • `apply_icon_to_window(window, icon_path)` — Force `icon_path` onto `window`'s title bar AND taskbar entry.
    • `apply_chrome(window, icon_path)` — Convenience: dark title bar + icon, in one call. Call from
    • `cancel_chrome_callbacks(window)` — Cancel any pending `apply_chrome` / `apply_icon_to_window`

### ui/dialogs/ — dialogs
- `ui/dialogs/ai_health.py` — ai_health.py — AI Health & Quota dialog.
    • `class AIHealthDialog` — Standalone window — Tier + Usage + History + Pre-flight + Recent calls
        ↳ destroy, refresh
- `ui/dialogs/pairing.py` — pairing.py — the QR a phone scans to pair with this PC.
    • `class PairingDialog` — Shows the pairing QR and what the receiver is doing.
    • `current_ship()` — The vessel this PC files for. Remembered, because it is asked once and
- `ui/dialogs/settings.py` — settings.py — Settings dialog (model, UI scale, auto-update toggle). Since
    • `class SettingsDialog` — Modal dialog for the AI model, UI scale and update-check setting, saved to the app config.
        ↳ destroy

### installer/ — the setup program
- `installer/build_installer.py` — build_installer.py — Build pipeline for installer.exe
    • `zip_payload()` — Zip the built app folder in dist/ into the payload zip, or exit if the app is not built.
    • `build_installer()` — Run PyInstaller on the installer spec to build dist/HappyPhotoOrganizerSetup.exe.
    • `main()` — Zip the payload, build the installer exe and print its size.
- `installer/installer.py` — Happy Photo Organizer — Setup (Creative Single-Page Hero)
    • `enable_paste(widget)` — Make Ctrl+V / right-click → Paste work on Thai keyboard layout.
    • `get_payload_path()` — Find the payload (zipped main app folder) bundled with installer.
    • `get_asset(name)` — Return the path of a bundled asset by name, or None if it does not exist.
    • `class GradientBackground` — Canvas that paints animated gradient + sparkles
        ↳ start, stop
    • `class Installer` — Handles actual install steps — copy payload, create shortcuts, save settings
        ↳ install, launch_app
    • `class SetupWindow` — Installer window that walks through setup options, install progress and the done screen.
    • `desktop_shortcut_path()` — The Desktop the shell really uses — it can be redirected (OneDrive, a
    • `start_menu_shortcut_path()` — The Start Menu shortcut path in the current user's Programs folder (under APPDATA).
    • `main()` — Entry point: --fresh-into for the drill, --silent/--upgrade headless, else the setup window.

### tools/ — release and commit tooling
- `tools/gen_codemap.py` — gen_codemap.py — write layer B of docs/CODEMAP.md from the code itself (rule #15).
    • `class CodemapError` — docs/CODEMAP.md is missing, or its markers are not exactly one pair.
    • `first_doc_line(node)` — The first line of a node's docstring, or "" when it has none.
    • `signature(node)` — Name plus argument names, without types or defaults.
    • `scan_file(path, root)` — Markdown lines for one module: its path and summary, then its public names.
    • `files_of(root, rel)` — The .py files a section covers, sorted; __init__.py is skipped.
    • `build_auto(root)` — Layer B: every section's modules and their public functions and classes.
    • `render(root)` — (current text, text with layer B regenerated); LF line ends in both.
    • `is_fresh(root)` — True when layer B already matches the code.
    • `main(argv)` — Rewrite layer B, or with --check only report whether it is stale.
- `tools/key_guard.py` — key_guard.py — never let a Gemini key reach git (Nick, 2026-10-31; house rule
    • `needles()` — The registered key as bytes ([] where there is no embed-key file, e.g.
    • `holds_key(raw, extra)` — True if raw matches a Google key shape or holds a needle (the registered key unless extra).
    • `scan_index(root)` — Paths whose STAGED content holds a key. Raises on any git failure.
    • `main(argv)` — Run the scan argv asks for (--index or --message FILE); 0 clean, 1 key or error, 2 usage.
- `tools/publish_release.py` — publish_release.py — publish a release through gates that refuse.
    • `class Refused` — A gate said no. Nothing after it runs.
    • `class NotYetKnown` — No verdict yet: GitHub has not caught up, or did not answer.
    • `settle(gate, delays, sleep)` — Run `gate()` until it gives a verdict, asking again while it raises
    • `run(args, timeout)` — Run a command and return its stdout. **Never pipes, and never swallows.**
    • `gate_tree_is_clean(runner)` — Nothing uncommitted, and local main is neither ahead of nor behind origin.
    • `gate_version_agrees(version, bundled)` — VERSION, and the version INSIDE the thing that was built, must match.
    • `gate_readme_names_this_version(version, readme)` — README.md's Version line must name the version being released (rule #15).
    • `gate_codemap_is_fresh(root)` — docs/CODEMAP.md layer B must match the code as committed (rule #15).
    • `gate_bundle_is_not_stale(installer, bundled)` — The installer must be newer than every tracked source file.
    • `sha256_file(path)` — The file's SHA-256 as lowercase hex, read in 1 MiB chunks.
    • `gate_a_drill_saw_these_bytes(tag, installer, runner)` — Rule #28: no update drill, no release. Asked FIRST, before a tag or a
    • `gate_asset_is_named_correctly(installer)` — The auto-updater matches on this exact name (updater.py:33). A renamed
    • `gate_published(version, expect_bytes, fetch, expect_sha256)` — After publishing: is it REALLY there, and is it the right bytes?
    • `app_logs_elsewhere()` — The two gates below run the APP's updater on this PC, which is also an
    • `gate_the_app_would_offer_it(version, previous, expect_sha256)` — Ask the APP, not the API. The updater is the only consumer that matters,
    • `gate_the_download_is_the_drilled_file(version, expect_sha256)` — §5.7: re-download the asset the way the field does — through the app's
    • `local_gates(version)` — Every gate that needs no network beyond git; returns the installer's size.
    • `publish(version, previous, notes)` — Gate, tag, upload as a draft, verify, publish, then read it all back from outside.
    • `main()` — Publish the version in VERSION, or --check / --dry-run; 1 on a refusal.

### scripts/ — one-off maintenance scripts
- `scripts/build_catalog.py` — build_catalog.py
    • `extract_job_name(folder_name)` — ตัดเลขลำดับ + วันที่นำหน้าออก คืนชื่องานสะอาด + วันที่ (ถ้ามี)
    • `normalize(name)` — normalize ชื่อสำหรับ deduplicate — lowercase, ลบ extra space, normalize 'No.'
    • `extract_keywords(name)` — ดึง keyword หลักจากชื่องาน — ใช้สำหรับ AI matching
    • `is_month_folder(name)` — เช็คว่าเป็นโฟลเดอร์ระดับเดือนมั้ย เช่น 'May 26', 'DEC 2025', 'JAN 2026'
    • `scan_source(source, jobs)` — สแกน 1 source — return จำนวน job dirs ที่เจอ
    • `register_job(raw_name, ship, month, jobs)` — ลงทะเบียน 1 job dir ลงใน jobs catalog
    • `main()` — Scan every SOURCES ship folder and write the deduplicated job catalog to OUTPUT_PATH.
- `scripts/gen_assets.py` — gen_assets.py — สร้าง logo + icon ของ Happy Photo Organizer
    • `make_logo(size)` — Draw the app logo (gradient circle, glow, camera glyph, sparkle) as a square RGBA image.
    • `main()` — Write the large and small logo PNGs and the multi-size happy_icon.ico into assets/.
- `scripts/import_job.py` — import_job.py — file a job folder that came off the phone (JobShot), no UI.
    • `main(argv)` — Parse the command line, file the JobShot job folders it names, and return an exit code.
- `scripts/smoke_test.py` — smoke_test.py — LIVE integration smoke test (real Gemini call).
    • `section(title)` — Print a banner heading for the next smoke-test step.
    • `test_auth()` — Check a key is set, a client builds and the live connection works; list some vision models.
    • `test_catalog()` — Load the job catalog and check that find() round-trips on its first name.
    • `test_exif(samples)` — Print the capture date and its source for up to three sample images.
    • `test_resizer(samples)` — Resize the first sample to a temp file, report the size change, then delete the copy.
    • `test_grouper(samples)` — Group the samples into shooting sessions and check that at least one comes out.
    • `test_analyzer(samples)` — Send the first sample and up to 30 job names to live Gemini Vision and check the reply parses.
    • `main()` — Run every smoke-test step, print a pass/fail summary, and return 1 if any step failed.
<!-- CODEMAP:AUTO:END -->
