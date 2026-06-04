# MEMORY.md — Happy Photo Organizer

> สแนปช็อต onboarding หลักของโปรเจคนี้ (ไฟล์เดียว) — Nick สั่ง "อ่านเมมโมรี่" = อ่านไฟล์นี้
> สร้างจากการ onboard ตาม MASTER Section 5 เมื่อ **2026-06-04** | Version ปัจจุบัน: **v1.041** (Tester round)
> ✅ **Re-verified 2026-06-04** (session ใหม่ — วัดกับโค้ดจริง ไม่ใช่จำ): 32 files · 7,198 LOC · core 15 · ui 7 · main.py 1,240 · catalog 146 (121 bundled + 25 user) · 14 formats · `tests/test_core.py` 27/27 PASS — **ทุกตัวเลขตรงกับเมมโมรี่** (แก้จุดเดียว: main.py ~1,245 → 1,240)

---

## หมวด A — Path ของระบบหลัก

| ไฟล์ | Path |
|------|------|
| MASTER.md | `C:\Users\NickSuksanTr\Documents\Claude\Projects\Nick\MASTER.md` |
| SHARED.md | `C:\Users\NickSuksanTr\Documents\Claude\Projects\Nick\SHARED.md` |
| command_pattern.md | `C:\Users\NickSuksanTr\Documents\Claude\Projects\Nick\command_pattern.md` |
| Note Master.txt | `C:\Users\NickSuksanTr\Documents\Claude\Projects\Nick\Note Master.txt` |
| **โปรเจคนี้** | `C:\Users\NickSuksanTr\Documents\Projects\Happy-Photo-Organizer\` |

- วันที่อ่าน MASTER ครั้งล่าสุด: **2026-06-04** (context fresh)
- ⚠️ กฎ MASTER: หลังอ่าน+บันทึกเสร็จ → **ปิดไฟล์กลางทั้ง 4 ทุกครั้ง** (คอส + Coddy ใช้ไฟล์ชุดเดียวกัน)

---

## หมวด B — Gemini & AI Settings

| Setting | ค่า |
|---------|-----|
| Default Model | `gemini-3.1-flash-lite` (ห้ามเปลี่ยนเป็น Vertex / ห้าม hard-code free-only) |
| API Key Type | Google **AI Studio** เท่านั้น |
| Rate Limit | **RPM 15 / TPM 250,000 / RPD 500** (free tier) — เตือน Nick ก่อน batch ใหญ่ |
| Key location | `~/.happy-photo-organizer/auth.json` (atomic JSON, ไม่ hard-code ใน code) |

- ก่อนยิง Gemini เยอะ ต้องถาม Nick: (1) call กี่ครั้ง (2) free/paid key (3) ถ้าเกิน 500 RPD ต้อง throttle/split
- Settings ในแอปต้องให้เลือก pro/paid model ได้เสมอ
- รายละเอียด: ดู `GEMINI_LIMITS.md` ในโปรเจค

---

## หมวด C — Tools & Environment (จาก SHARED, ที่ใช้ในโปรเจคนี้)

| Tool | เวอร์ชัน |
|------|---------|
| Python | 3.13.13 (`...\Python313\python.exe`) |
| google-genai (Gemini SDK) | 1.75.0 |
| CustomTkinter | 5.2.2 (+ tkinterdnd2) |
| Pillow + pillow-heif | (รองรับ HEIC/iOS, 14 formats) |
| PyInstaller | 6.20.0 (folder mode) |
| Inno Setup | 6 (`ISCC.exe`) |
| Git | 2.54.0 |

---

## หมวด D — command_pattern 11 ข้อ (Quick Reference)

1. **Project Boundary** — ทำงานแค่ในโฟลเดอร์โปรเจคนี้ · โปรเจคอื่นอ่านได้/เอา idea ได้ แต่ห้ามแก้
2. **Gemini** — AI Studio key เท่านั้น · default `gemini-3.1-flash-lite` · RPM15/RPD500 · เตือนก่อน batch ใหญ่
3. **Branding** — Icon (camera) = Identity (taskbar/installer) · Mascot (robot) = Helper (welcome/dropzone) · ห้ามสลับ
4. **อัปเดต MEMORY** เมื่อพบ bug / code เสี่ยงสูง — ระบุ file/function/line + วิธีแก้
5. **Tester** trigger → spawn 3 agent ขนาน (functional gaps / code correctness / holistic) → แก้ทันทีไม่รอ approve → test → build → อัปเดต memory → รายงาน + สรุป token
6. **จัดโฟลเดอร์ให้เป็นระเบียบ** — มี `_trash\` (แยกหมวด, ห้ามลบตรงๆ ให้ย้าย)
7. **Changelog/log/bug** — แยกโฟลเดอร์ · max 20 entries/ไฟล์ · max 10 ไฟล์/ระบบ · เกินโยน `_trash`
8. **อ่าน memory (log/bug/changelog)** สูงสุด 5 ไฟล์ล่าสุด (=100 entries) ยกเว้น Nick สั่งอ่านหมด
9. **Log** — บันทึกการคุย+คำสั่งแยกตาม version ใน `log\log_vX.md`
10. **Bug Log** — บันทึก bug+fix แยกตาม version ใน `bug\bug_vX.md`
11. **V-Log** — timeline ทุกเวอร์ชันใน `V-Log.md`

> หมายเหตุ: ข้อ 7–8 (log/bug/changelog หมุนตาม version) = คนละตัวกับ MEMORY.md (สแนปช็อตไฟล์เดียวนี้)

### กฎเสริมจาก Note Master.txt (Nick เขียนเอง)
- บันทึกทุกอย่างใน**โฟลเดอร์โปรเจคนี้เท่านั้น** · ทุกครั้งที่อัปเดต → **รันเทส + บันทึกลง memory**
- มีโฟลเดอร์ `_trash\` (ไฟล์ไม่ใช้แล้ว) + โฟลเดอร์ **ผู้ใช้** (ไฟล์ส่งออกให้ user ที่ไม่เกี่ยวกับโค้ดแอป เช่น screenshot หน้าตาแอป) — อย่าวางกระจัดกระจาย
- ก่อนเริ่มงาน: อ่าน md ในโปรเจคก่อน + ดูวิธีทำงานครั้งก่อนๆ
- จบงานทุกครั้ง: **สรุปงาน + อัปเดตให้ Nick รู้**
- ไม่จำกัด token/agent — ออกแบบให้ agent ทำงานขนานได้
- (เฉพาะแอปมือถือ: ตั้งชื่อ APK/AAB ชัดเจน + version, รันเทสใน emulator ก่อน build ขึ้น Play — *โปรเจคนี้เป็น desktop ไม่ใช้*)

### 🔀 Git workflow (Nick สั่ง 2026-06-04 — override ของเดิม)
- **เลิก PR/feature-branch — ทำงานบน `main` ตรงๆ** (เดิม `tester/* → PR → merge`; ปิดแล้ว — branch `tester/v1.041-audit-fixes` + PR #1 ลบ/ปิดทั้ง local+remote)
- **commit + push + build + ปล่อย GitHub Release ได้เลย ไม่ต้องถาม** — Nick ให้ standing authorization ("อัพขึ้นเลยตามปกติ ไม่ต้องถาม") → ทำ flow ปกติ (ดู RELEASE.md) แล้วรายงานท้าย

---

## หมวด E — สิ่งที่ต้องอัปเดต SHARED

- **ไม่มี** — SHARED.md (last updated 2026-06-03) ยังตรงกับความจริง: Python 3.13.13, google-genai 1.75.0, CustomTkinter 5.2.2, PyInstaller 6.20.0 ตรงกับที่โปรเจคใช้

---

## 📸 Project Snapshot (สำหรับ session ใหม่เข้าใจเร็ว)

**คืออะไร:** AI photo organizer สำหรับงานซ่อมบำรุงเรือ — drop รูป → auto date → resize 10-25KB → group by day → AI tag ชื่องาน (Gemini Vision) → review → rename folder `DD-MM-YY <Job>`

**Tech:** customtkinter 5.2 + tkinterdnd2 · google-genai (Gemini 3.1 Flash Lite) · Pillow + pillow-heif · PyInstaller + custom installer

**ไฟล์ AI สำคัญ (สำหรับงานเทส AI):**
- `core/analyzer.py` — Gemini Vision calls, `_is_transient_error` (regex 5xx), 5xx retry exponential backoff, Thai→EN translate, fuzzy catalog match (cutoff 0.85)
- `core/processor.py` — Phase 2 orchestration (parallel 4 workers ThreadPoolExecutor), date detection/allocation
- `core/rate_limiter.py` — tier presets + custom RPM/RPD + cancel-aware throttle + quota tracking (PT 00:00 reset)
- `core/catalog.py` — `data/job_catalog.json` (146 jobs), atomic save, RLock
- `core/auth.py` — API key (atomic auth.json + quarantine)
- `scripts/smoke_test.py` — มี smoke test (tests ใช้ stub `google.genai` — **AI จริงเทสได้แค่บนเครื่อง Nick + key จริง**)

**สถานะ:** v1.041 · **7,198 LOC / 32 ไฟล์** (core 15 + ui 7 modules, main.py 1,240) · catalog **146 (121 bundled + 25 user)** · 14 formats · ผ่าน audit 8 รอบ (Cos) + **Tester round v1.041** (3-agent, 18 code fixes)
**Tests (จริง):** `tests/test_core.py` = **27/27 PASS** (pure-Python, ไม่ต้องใช้ key/รูป) · `scripts/smoke_test.py` = live Gemini smoke 6/6 (มี synthetic-image fallback). ⚠️ คำว่า "67/67 tests" ใน docs เก่า = ของปลอม (ไม่เคยมี test suite) — แก้แล้ว
**Tester v1.041 fixes สำคัญ:** grouper ข้ามเที่ยงคืน · date allocation เดือนเต็มเก็บวัน EXIF เดิม · analyzer JSON raw_decode · tier→model wiring · auth null-safe · settings scale revert on Cancel · installer atomic auth.json · Thai→EN strings

**Build/Release:** `dist/HappyPhotoOrganizerSetup.exe` (82.7 MB / 86,752,959 B) · **v1.041 ปล่อยขึ้น GitHub Releases แล้ว 2026-06-04** → `/releases/latest` = v1.041 (auto-updater เห็น, ไม่ใช่ prerelease) · tag `v1.041` → dca0706 · local `main` sync = 1.041 แล้ว · auto-updater ผ่าน GitHub Releases API

**Known limitations:** Phase 1 ช้ากว่า Nick_Resizer 5-10x (iterative quality) · AI accuracy ขึ้นกับ catalog completeness · ไม่มี undo Phase 4 · ทดสอบ AI จริงต้องมี key + รูปจริง

**V2 roadmap:** เติม .docx form อัตโนมัติจากชื่อโฟลเดอร์ + AI-generated รายละเอียดงาน (python-docx/docxtpl) — รอ Nick ยืนยันก่อนเริ่ม

**Branding (อย่าสับสน):** 📷 camera (`happy_icon.ico`, `happy_logo*.png`) = identity · 🤖 robot (`mascot.png`) = helper

**อย่าทำ (decided):** ห้าม revert UI Thai · ห้ามเอา mascot ไปช่อง identity · ห้ามเปลี่ยน default model · ห้ามใส่ bounce animation mascot · ห้ามลบ uninstaller/registry · ห้าม refactor Phase 2 เป็น sequential
