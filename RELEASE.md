# Release Process — Happy Photo Organizer

## One-time setup (ครั้งเดียว)

### 1. สร้าง GitHub repo
- ไป https://github.com/new
- ชื่อ repo แนะนำ: `happy-photo-organizer` (หรืออะไรก็ได้)
- เลือก **Public** (ฟรี + ไม่ต้องใช้ token ใน app)
- ไม่ต้อง push source code ก็ได้ — แค่ใช้ Releases เป็น CDN

### 2. ตั้ง REPO ใน updater
แก้ไฟล์ [core/updater.py](core/updater.py) บรรทัด:
```python
REPO = os.environ.get("HAPPY_UPDATE_REPO", "<your-username>/<repo-name>")
```
ใส่ชื่อ owner/repo ของจริง เช่น `"nicksuksantr/happy-photo-organizer"`

หรือเซต env var ตอน build:
```powershell
$env:HAPPY_UPDATE_REPO = "nicksuksantr/happy-photo-organizer"
```

### 3. (Optional) สร้าง GitHub CLI token
```powershell
gh auth login
```
จะใช้ตอน `gh release create` ได้

---

## Per-release (ทุกครั้งที่ปล่อย version ใหม่)

### Step 1 — Bump version
**แก้ที่เดียว: ไฟล์ `VERSION`** (single source of truth).
- `main.py`, `installer/installer.py`, และ AI Health อ่านค่าผ่าน `core/version.py`
  (`read_version()` อ่านไฟล์ `VERSION`, รองรับ frozen bundle ผ่าน `sys._MEIPASS`)
- ❌ **ไม่มี** `APP_VERSION = "..."` literal ใน main.py / installer แล้ว (ตั้งแต่ v1.029) —
  อย่าไปไล่หาแก้ในโค้ด
- (Optional) อัปเดตบรรทัด `**Status:** vX.XXX` ใน `PROJECT_SUMMARY.md` ให้ตรงกัน

### Step 2 — Build
```powershell
cd C:\Users\NickSuksanTr\Documents\Projects\Happy-Photo-Organizer
pyinstaller HappyPhotoOrganizer.spec --noconfirm --clean
python installer/build_installer.py
```

ผลลัพธ์: `dist/HappyPhotoOrganizerSetup.exe` (~80 MB)

### Step 3 — Test locally
1. รัน `dist/HappyPhotoOrganizerSetup.exe` ติดตั้งทับเครื่องตัวเอง
2. เปิดแอป — ตรวจสอบเวอร์ชันที่ header เป็น v1.026 ใหม่
3. ทดสอบ feature ที่แก้ใหม่

### Step 4 — Create GitHub Release

**Via GitHub CLI (เร็วสุด):**
```powershell
gh release create v1.026 dist/HappyPhotoOrganizerSetup.exe `
  --title "v1.026 — <สั้นๆ ว่าแก้อะไร>" `
  --notes-file release-notes.md
```

**Via Web UI:**
- ไป `https://github.com/<owner>/<repo>/releases/new`
- Tag: `v1.026` (ต้องขึ้นต้นด้วย v)
- Title: `v1.026 — Date allocation fix`
- Description: markdown bullet points
- Drag-drop `dist/HappyPhotoOrganizerSetup.exe` ลงช่อง assets
- กด "Publish release"

### Step 5 — เครื่องอื่นๆ
- เครื่องที่ลง v1.025+ ติดตั้งแล้ว → next startup จะเช็คเอง → popup
- เครื่องที่ลง v1.024 (ก่อน updater) → ต้อง manual download installer ครั้งสุดท้าย

---

## Version numbering convention

- Format: `1.MAJOR_OR_BUILD` (เช่น 1.039, 1.040, 1.041)
- Tag ต้องขึ้นต้นด้วย `v` (เช่น `v1.041`) — updater strip `v` ออกอัตโนมัติ
- เปรียบเทียบแบบ **per-segment integer tuple** (ผ่าน `updater.is_newer` → `_parse_version`):
  `"1.041"` → `(1, 41)`, แล้ว pad ความยาวให้เท่ากันก่อนเทียบ → `(1,41) > (1,40)` ✓

## Asset naming

Installer **ต้องชื่อ** `HappyPhotoOrganizerSetup.exe` เป๊ะ — ตรงกับ `INSTALLER_ASSET_NAME` ใน updater.py

ถ้าจะเปลี่ยนชื่อ → แก้ใน [core/updater.py](core/updater.py) เช่นกัน (`INSTALLER_ASSET_NAME` constant)

---

## Troubleshooting

### Updater ไม่เจอ release ใหม่
1. ลอง browser เปิด `https://api.github.com/repos/<owner>/<repo>/releases/latest` → ดูว่ามี JSON release จริงมั้ย
2. ตรวจ `REPO` ใน updater.py ตรงกับ repo จริง
3. ตรวจ tag เริ่มด้วย `v` (เช่น `v1.026` ไม่ใช่ `1.026`)
4. ตรวจ release ไม่ใช่ "Pre-release" — updater ดึงเฉพาะ stable

### Silent install ล้มเหลว
- เครื่องไม่มี admin → install ลง `%LOCALAPPDATA%` แทน Program Files (default แล้ว) → OK
- App กำลังเปิดอยู่ → installer พยายาม taskkill ก่อน แต่อาจช้า — wait 1-2s
- Antivirus block → user ต้อง whitelist installer

### Build ผิดพลาด
- ลอง `python installer/build_installer.py` ตรงๆ → ดู error
- ตรวจว่า `pyinstaller` version ตรงกัน (`pip install pyinstaller==6.20.0`)
