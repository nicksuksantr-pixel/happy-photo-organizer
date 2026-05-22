# 🎨 Happy Photo Organizer — Project Summary

**Status:** v1.031 (2026-05-22 — dialog dark-bg fix + unused-import cleanup; v1.030 split main.py → core/+ui/)
**Author:** Nick (with Codey — Claude Code)
**Family:** Happy AI Family (siblings: HAPPY AI Agent)

---

## 📋 What it does

AI-powered photo organizer for ship maintenance & repair work:
1. Drop folders/photos → auto-detect capture date
2. Resize to 10–25 KB (target for email attachments)
3. Group by day + AI tag job name (Gemini Vision)
4. Review & edit before commit
5. Rename folders as `DD-MM-YY <Job Name>`

---

## 🏗 Tech Stack

| Layer | Choice |
|---|---|
| GUI | customtkinter 5.2 + tkinterdnd2 |
| AI | google-genai (Gemini 3.1 Flash Lite default) |
| Image | Pillow + pillow-heif (HEIC/iOS support) |
| Distribution | PyInstaller (folder mode) + custom installer |
| Storage | JSON files + Windows registry |

---

## 🎯 Features delivered (v1.024)

### Core workflow
- ✅ Drag-drop multi-source (folders + files)
- ✅ Recursive image collection (14 formats incl. HEIC)
- ✅ EXIF + filename + mtime date detection
- ✅ Resize 10-25 KB iterative quality
- ✅ Group by date + time gap (90 min)
- ✅ Smart date allocation (v1.026): consolidate ทุก assignment ไปยัง dominant month ของ dest_root + เลขวัน unique ข้ามทุกเดือน + earliest-gap-first (ใช้ EXIF day ถ้าว่าง, ไม่งั้น scan from day 1) + range pattern `DD-DD.MM.YY` + cap วันสุดท้ายเมื่อเต็ม
- ✅ Auto-updater (v1.025): silent startup check ผ่าน GitHub Releases API + in-app download progress + silent install + relaunch
- ✅ Layout refactor (v1.027): Log panel ย้ายไปคอลัมน์ขวา (เต็มความสูง), Step 1+2 stacked ทางซ้าย
- ✅ Drop-zone idle border subtle grey (v1.027): ไม่โชว์ highlight สีส้มตอนเปิดแอป — เปลี่ยนสีเฉพาะตอน drag enter
- ✅ Window state persist (v1.027): จำขนาด/ตำแหน่ง/maximized state ระหว่าง session — เก็บใน `~/.happy-photo-organizer/auth.json` field `window_state`
- ✅ System tray (v1.028): pystray icon ที่ system tray ขวาล่าง — เมนู Show / Check for updates now / Quit
- ✅ Hide-to-tray on X (v1.028): กดปุ่ม X ปิด window → withdraw ไป tray (ไม่ exit); ออกจริงผ่าน tray menu "Quit" เท่านั้น
- ✅ Background auto-update (v1.028): เช็คทุก 5 นาที (รวมเมื่อ window hidden) → ถ้าพบใหม่ → silent download → silent install + relaunch (ไม่มีปุ่มกด)
- ✅ Single-instance lock (v1.028): Win32 named mutex ป้องกัน HPO ซ้ำ; ถ้ามีอยู่แล้ว → ดึง window เดิมกลับมาจาก tray

### AI
- ✅ Gemini Vision per-folder sampling (1-3 photos)
- ✅ Fuzzy match catalog (cutoff 0.85)
- ✅ Translate Thai → English job names
- ✅ Auto-add new names to catalog
- ✅ Rate Limiter (tier presets + custom RPM/RPD)
- ✅ Quota tracking with PT 00:00 reset
- ✅ Parallel Phase 2 (4 workers via ThreadPoolExecutor)

### UI
- ✅ Single-window 2-column layout (Step 1 + 2 side-by-side)
- ✅ Step status indicators (Pending/Ready/Running/Done) via Canvas oval
- ✅ Live log panel with realtime updates
- ✅ AI Health dialog (usage bars, 7-day history, recent calls, pre-flight calculator)
- ✅ Header badge with live RPM tracking (refresh every 2s)
- ✅ Camera icon = app identity / Robot mascot = guide character
- ✅ Clickable URLs to AI Studio
- ✅ UI Scale slider (0.7x – 1.3x)
- ✅ Pro English copy throughout

### Installer (creative)
- ✅ Single-page Hero design (no wizard nav)
- ✅ Animated gradient background + sparkles
- ✅ License + Tips panel during install (not boring)
- ✅ Smooth progress (every file update, 0–100% smooth)
- ✅ API key setup during install (optional)
- ✅ Desktop shortcut + Start Menu integration
- ✅ Uninstaller (uninstall.bat + HKCU registry)
- ✅ Add/Remove Programs entry

---

## ⚖ Pros & Cons

### 🟢 ข้อดี
- **Workflow ฉลาด** — resize ก่อน แล้ว AI sample → ไม่เปลือง quota (1 call/folder ไม่ใช่ 1 call/photo)
- **Predictable size** — target 10-25 KB ทำให้ไฟล์ใส่ email ได้แน่นอน
- **Format coverage กว้าง** — รองรับทั้ง iOS (HEIC), Android (WEBP), DSLR (TIFF)
- **Rate limiter ครอบคลุม** — ทั้ง free preset และ custom + paid mode
- **Smart date** — แผนกอื่นใช้วันที่ไหนแล้วเรา avoid ให้
- **AI Health page** — เห็น quota + history + simulate
- **Creative installer** — ไม่ใช่ wizard เก่าๆ
- **HAPPY family branding** — consistent กับ HAPPY AI Agent

### 🟡 ข้อจำกัด / ข้อเสีย
- **Phase 1 ช้ากว่า Nick_Resizer 5-10x** — เพราะ iterative quality reduction (5-15 encode/รูป)
- **Installer size 80 MB** — Python + bundled libs ใหญ่ (แลกกับ no install dependencies)
- **AI accuracy ขึ้นกับ catalog completeness** — งานใหม่ที่ไม่เคยมี → ต้องพิมพ์เอง
- **No undo Phase 4** — rename แล้วต้อง revert manually (ของ defer ของคอส)
- **Mascot mild distortion** — CTkImage scaler ตัดแขนนิดหน่อย (=signature ของ HAPPY mascot)

### 🐛 ข้อผิดพลาดในการเขียน (lessons learned)

| Bug | Root cause | Fix |
|---|---|---|
| Phase 2 returns "list has no setdefault" | Gemini ตอบ JSON array ไม่ใช่ object | parse → coerce to dict (`_parse_json_response`) |
| Mascot/progress bar ทับซ้อน | mix `place_configure` + `pack` | drop bounce animation, use pack throughout |
| Mascot แขนตัด | `CTkImage(size=)` runtime scaler quality ต่ำ | pre-resize ด้วย `PIL.Image.resize(LANCZOS)` |
| Ctrl+V ไม่ paste บน Thai keyboard | Tk default ใช้ keysym `<Control-v>` → TH = `<Control-ฬ>` | bind ด้วย **keycode** (scancode 86) แทน keysym |
| Bind on CTkEntry ไม่ trigger | CTkEntry wrap tk.Entry → bind ที่ outer ไม่ได้ผล | bind ที่ `widget._entry` (internal) |
| Deadlock ใน snapshot() | `RLock` nested calls ใช้ Lock | switch to `threading.RLock()` |
| Settings dialog freeze 2-5s | API call blocking main thread | move to `threading.Thread` + `self.after()` |
| Step circle 1/2/3 เบี้ยว | CTkFrame `corner_radius` ไม่ใช่ true circle | use `tk.Canvas.create_oval()` |
| Tier ไม่ persist | save_config ไม่รู้จัก field tier | merge full config + write_text directly |
| Tkinter after() callback warnings | scheduled callbacks ค้างตอน destroy | override `destroy()` + `after_cancel()` |
| Smart date ข้ามวันว่าง + ทับ range folder (v1.025) | `assign_unique_dates()` forward-shift only + regex ไม่ detect `DD-DD.MM.YY` (เช่น "15-17.05.26 Job MD") | bidirectional search (-1, +1, -2, +2, ...) tie-break ย้อนหลัง + เพิ่ม `_FOLDER_DATE_RANGE_RE` expand range เป็น set ของวัน |
| Date เบิ้ลข้ามเดือน + ข้าม gap (v1.026) | bidirectional respect EXIF month → photos เดือนคนละเดือน (มี.ค.) ถูก assign ใน dest April → เลขวันซ้ำ "17-03" + "17-04"; bidirectional หา nearest ทำให้ข้าม gap 3-7 ที่ห่างจาก EXIF day | 1. `scan_used_days()` คืน set[int] day numbers ข้ามทุกเดือน → unique 2. `detect_target_month()` หา month ที่ปรากฏมากที่สุดใน dest → consolidate ทุก assignment ไป month นั้น 3. `_find_free_day_earliest()` แทน bidirectional — ใช้ EXIF day ถ้าว่าง, ไม่งั้น fill gap จาก day 1 |

---

## 📦 Build artifacts

```
Documents/Projects/Happy-Photo-Organizer/
├── main.py                                   (50 KB, v1.024)
├── core/                                     (8 modules)
├── data/job_catalog.json                     (138 jobs)
├── assets/
│   ├── happy_icon.ico                        (camera, 46 KB)
│   ├── happy_logo.png                        (camera, 17 KB)
│   ├── mascot.png                            (HAPPY robot, 13 KB)
│   └── mascot_with_text.png                  (22 KB — for installer bg)
├── installer/
│   ├── installer.py                          (creative setup)
│   ├── build_installer.py                    (pipeline)
│   └── HappyPhotoOrganizerSetup.spec
├── HappyPhotoOrganizer.spec
└── dist/
    ├── HappyPhotoOrganizer/                  (120 MB, 1828 files)
    │   └── HappyPhotoOrganizer.exe           (12 MB)
    ├── HappyPhotoOrganizer.zip               (48 MB payload)
    └── HappyPhotoOrganizerSetup.exe          (80 MB ← share this)
```

---

## 🎨 Icon vs Mascot (สำคัญ — อย่าสับสน)

| ของ | ใช้ที่ | ความหมาย |
|---|---|---|
| 📷 **Camera** (`happy_icon.ico`, `happy_logo*.png`) | • Windows taskbar / title bar<br>• Header logo ในแอป<br>• Installer.exe icon<br>• Desktop shortcut | **Identity** ของแอป Happy Photo Organizer |
| 🤖 **HAPPY robot** (`mascot.png`) | • Welcome screen ของ installer<br>• Drop zone (50% fade)<br>• ปุ่ม Start AI Tagging / Commit Rename | **Helper character** — guide การใช้งาน (มาตรฐาน Happy AI Family) |

**❌ อย่าใช้ mascot ในตำแหน่ง identity** — Desktop จะซ้ำกับ HAPPY AI Agent
**❌ อย่าใช้ camera ในตำแหน่ง helper** — เสีย branding ของ HAPPY family

---

## 🚀 V2 Roadmap (next session)

**Concept:** เอาชื่อโฟลเดอร์ (DD-MM-YY <Job>) + รายละเอียด → กรอก form เอกสารอัตโนมัติ

### Features ที่จะทำ V2
- [ ] อ่าน folder name → parse date + job name
- [ ] Match กับ form template ที่มีอยู่ (.doc / .docx)
- [ ] เติม fields:
  - วันที่ทำงาน
  - ชื่องาน
  - รายละเอียดเพิ่ม (จาก AI วิเคราะห์รูป)
  - ผู้ปฏิบัติงาน / เรือ / แผนก
- [ ] Batch generate หลาย form จากหลายโฟลเดอร์ทีเดียว
- [ ] Output: .docx ที่กรอกแล้ว + อาจ embed รูปลง form

### Dependencies ที่อาจต้องการ
- `python-docx` — read/write .docx
- `docxtpl` — Jinja-style templating
- AI ช่วยสรุป "รายละเอียดงาน" จากรูป
- F-04-TEC-03 Engine Maintenance Report template

### ความท้าทาย V2
- Template parsing (placeholders / merge fields)
- Embedding รูปลง .docx ตามขนาด/ตำแหน่ง
- Multi-language (TH report + EN folder name)

→ ค่อยคุยรายละเอียดตอนเริ่ม V2 session

---

## 🙏 Credits

**Made by Nick** (ENA Crystal AHTS DP2 Electrician)
**Coded with Codey** (Claude Code in this session)
**Mascot design by Cos** (Claude in app — HAPPY AI Family)

Session date: 2026-05-17 → 2026-05-18
Total iterations: v1.001 → v1.024 (24 versions)
