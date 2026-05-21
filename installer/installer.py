"""
Happy Photo Organizer — Setup (Creative Single-Page Hero)

Design:
  • One screen, no wizard navigation
  • Animated gradient background (subtle ส้ม-ชมพู pulse)
  • Mascot character bounces gently
  • Sparkles fade in/out on canvas
  • Hero card with shadow
  • Smooth phase transitions: Setup → Installing → Done
"""
from __future__ import annotations

import json
import os
import random
import shutil
import sys
import threading
import time
import webbrowser
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageDraw, ImageFilter


def enable_paste(widget):
    """Make Ctrl+V / right-click → Paste work on Thai keyboard layout.
    Bind via keycode (scancode) on the inner tk.Entry of CTkEntry/CTkComboBox.
    """
    KEYCODE_V = 86
    KEYCODE_C = 67
    KEYCODE_X = 88
    KEYCODE_A = 65

    target = getattr(widget, "_entry", widget)

    def do_paste(_e=None):
        try:
            text = target.clipboard_get()
        except tk.TclError:
            return "break"
        try:
            target.delete("sel.first", "sel.last")
        except Exception:
            pass
        try:
            target.insert("insert", text)
        except Exception:
            pass
        return "break"

    def do_copy(_e=None):
        try:
            sel = target.selection_get()
            target.clipboard_clear()
            target.clipboard_append(sel)
        except Exception:
            pass
        return "break"

    def do_cut(_e=None):
        try:
            sel = target.selection_get()
            target.clipboard_clear()
            target.clipboard_append(sel)
            target.delete("sel.first", "sel.last")
        except Exception:
            pass
        return "break"

    def do_select_all(_e=None):
        try:
            target.select_range(0, "end")
            target.icursor("end")
        except Exception:
            pass
        return "break"

    def on_ctrl(e):
        kc = e.keycode
        if kc == KEYCODE_V:
            return do_paste()
        if kc == KEYCODE_C:
            return do_copy()
        if kc == KEYCODE_X:
            return do_cut()
        if kc == KEYCODE_A:
            return do_select_all()

    def show_menu(e):
        m = tk.Menu(target, tearoff=0)
        m.add_command(label="Cut",   command=do_cut)
        m.add_command(label="Copy",  command=do_copy)
        m.add_command(label="Paste", command=do_paste)
        m.add_separator()
        m.add_command(label="Select All", command=do_select_all)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    target.bind("<Control-Key>", on_ctrl)
    target.bind("<Button-3>", show_menu)

# ─── Theme (match HAPPY family) ────────────────────────────────
COLOR_BG = "#0F172A"
COLOR_CARD = "#1E293B"
COLOR_CARD_LIGHT = "#334155"
COLOR_PRIMARY = "#FB923C"  # orange
COLOR_ACCENT = "#EC4899"   # pink
COLOR_TEXT = "#F1F5F9"
COLOR_MUTED = "#94A3B8"
COLOR_OK = "#10B981"
COLOR_WARN = "#F59E0B"
COLOR_DANGER = "#EF4444"

APP_NAME = "Happy Photo Organizer"
APP_EXE_NAME = "HappyPhotoOrganizer.exe"
APP_VERSION = "1.027"
DEFAULT_INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "HappyPhotoOrganizer"

LICENSE_TEXT = f"""Happy Photo Organizer
Personal Use License Agreement
Version {APP_VERSION}  —  2026-05-21
================================================================

Thank you for choosing Happy Photo Organizer.

1. License Grant
   • Provided free for personal use and learning.
   • Reselling or commercial redistribution requires written
     permission from the author (Nick Suksantr).

2. User Responsibilities
   • You must provide your own Gemini API key (free or paid).
   • All AI API costs are your responsibility.
   • This app does not collect or transmit your data,
     except as required to function (requests to Gemini API).

3. Warranty
   • Provided "as-is", no warranty.
   • The author is not liable for damages arising from use.
   • Please test in non-critical environments first.

4. Updates
   • No auto-update. Download new versions from:
     https://github.com/nicksuksantr/happy-photo-organizer
   • Updates are optional, not enforced.

5. Termination
   • Uninstall any time from Settings > Apps & features
     (or run uninstall.bat in install folder).
   • Your API key stays in ~/.happy-photo-organizer/auth.json —
     delete it manually if desired.

================================================================
💡 Tips while we install

  •  Drag & drop multiple folders at once — they'll be merged
  •  Press the "EN" button to translate Thai → English job names
  •  Click the camera icon in the header to open AI Health
  •  Pre-flight calculator estimates ETA before processing starts
  •  HAPPY robot guides you: drop zone → start → commit
  •  Custom RPM/RPD anytime — useful for paid Gemini keys
  •  Drop a folder on Step 1, then watch the workflow flow →

= = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
Made with ♥  by Nick & Codey (Happy AI Family)
"""

# Payload location (relative to this script when frozen or dev)
def get_payload_path() -> Path | None:
    """Find the payload (zipped main app folder) bundled with installer."""
    if hasattr(sys, "_MEIPASS"):
        # frozen — payload bundled via PyInstaller --add-data
        return Path(sys._MEIPASS) / "payload" / "HappyPhotoOrganizer.zip"
    # dev — refer to project's dist/ folder
    return Path(__file__).resolve().parent.parent / "dist" / "HappyPhotoOrganizer.zip"


def get_asset(name: str) -> Path | None:
    if hasattr(sys, "_MEIPASS"):
        p = Path(sys._MEIPASS) / "assets" / name
    else:
        p = Path(__file__).resolve().parent.parent / "assets" / name
    return p if p.exists() else None


# ─── Animated gradient background canvas ───────────────────────


class GradientBackground(ctk.CTkCanvas):
    """Canvas that paints animated gradient + sparkles"""

    def __init__(self, master, **kw):
        super().__init__(master, highlightthickness=0, bd=0, **kw)
        self.configure(bg=COLOR_BG)
        self._phase = 0.0
        self._sparkles: list[dict] = []
        self._after_id: str | None = None
        self.bind("<Configure>", self._on_resize)
        self._gradient_img_id = None
        self._render_pending = False

    def _on_resize(self, _ev):
        self._render()

    def start(self):
        self._tick()

    def stop(self):
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _tick(self):
        self._phase = (self._phase + 0.005) % 1.0
        # randomly spawn sparkles (~once per 0.5s avg)
        if random.random() < 0.04 and self.winfo_width() > 100:
            self._sparkles.append({
                "x": random.randint(20, max(21, self.winfo_width() - 20)),
                "y": random.randint(20, max(21, self.winfo_height() - 20)),
                "r": random.uniform(1.5, 3.5),
                "life": 0.0,
                "max_life": random.uniform(1.5, 3.0),
            })
        # advance sparkle life
        new_sparkles = []
        for s in self._sparkles:
            s["life"] += 0.05
            if s["life"] < s["max_life"]:
                new_sparkles.append(s)
        self._sparkles = new_sparkles
        self._render()
        self._after_id = self.after(50, self._tick)

    def _render(self):
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 4 or h < 4:
            return
        # build gradient image (PIL) — cached if size unchanged
        if (self._gradient_img_id is None) or self._last_size != (w, h):
            self._last_size = (w, h)
            img = Image.new("RGB", (w, h))
            draw = ImageDraw.Draw(img)
            # vertical gradient: navy top → subtle orange/pink hint bottom
            for y in range(h):
                t = y / max(h - 1, 1)
                # base color: navy at 0, slightly warmer at 1
                r = int(0x0F * (1 - t) + 0x28 * t)
                g = int(0x17 * (1 - t) + 0x18 * t)
                b = int(0x2A * (1 - t) + 0x38 * t)
                draw.line([(0, y), (w, y)], fill=(r, g, b))
            self._cached_gradient = img
        # subtle pulse via phase: shift overlay
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        # radial-ish soft glow at center-top
        from math import sin
        pulse = (sin(self._phase * 6.283) + 1) / 2  # 0..1
        glow_alpha = int(20 + 18 * pulse)
        glow_r = min(w, h) // 3
        cx, cy = w // 2, h // 4
        odraw.ellipse(
            (cx - glow_r, cy - glow_r, cx + glow_r, cy + glow_r),
            fill=(0xFB, 0x92, 0x3C, glow_alpha),
        )
        odraw.ellipse(
            (cx - glow_r // 2, cy + glow_r, cx + glow_r // 2, cy + 2 * glow_r),
            fill=(0xEC, 0x48, 0x99, glow_alpha // 2),
        )
        overlay = overlay.filter(ImageFilter.GaussianBlur(radius=min(w, h) // 12))
        composed = Image.alpha_composite(
            self._cached_gradient.convert("RGBA"), overlay,
        )
        # draw sparkles
        sd = ImageDraw.Draw(composed)
        for s in self._sparkles:
            life_ratio = s["life"] / s["max_life"]
            # fade in then out
            if life_ratio < 0.4:
                alpha = int(life_ratio / 0.4 * 220)
            else:
                alpha = int((1 - (life_ratio - 0.4) / 0.6) * 220)
            sd.ellipse(
                (s["x"] - s["r"], s["y"] - s["r"], s["x"] + s["r"], s["y"] + s["r"]),
                fill=(255, 240, 200, max(0, min(255, alpha))),
            )
        # apply to canvas
        self._tk_img = ctk.CTkImage(light_image=composed, dark_image=composed, size=(w, h))
        # use simple PhotoImage for canvas (CTkImage doesn't fit Canvas natively)
        from PIL import ImageTk
        self._photo = ImageTk.PhotoImage(composed)
        if self._gradient_img_id is None:
            self._gradient_img_id = self.create_image(0, 0, anchor="nw", image=self._photo)
        else:
            self.itemconfig(self._gradient_img_id, image=self._photo)


# ─── Installer Logic ───────────────────────────────────────────


class Installer:
    """Handles actual install steps — copy payload, create shortcuts, save key"""

    def __init__(self):
        self.install_dir: Path | None = None
        self.api_key: str = ""
        self.create_desktop_shortcut = True
        self.create_start_menu = True
        self.launch_after = True

    def install(self, progress_cb=None) -> tuple[bool, str]:
        """Execute full install. Returns (success, message)"""
        try:
            assert self.install_dir is not None
            # start at 0% so user sees it animate from beginning
            if progress_cb:
                progress_cb(0, "Starting install...")
                time.sleep(0.15)
                progress_cb(3, "Preparing install directory...")
            self.install_dir.mkdir(parents=True, exist_ok=True)

            payload = get_payload_path()
            if not payload or not payload.exists():
                return False, f"Payload not found: {payload}"

            if progress_cb:
                progress_cb(8, "Reading payload...")
                time.sleep(0.1)
                progress_cb(12, "Extracting application files...")
            with zipfile.ZipFile(payload, "r") as zf:
                members = zf.namelist()
                total = len(members)
                for i, member in enumerate(members):
                    zf.extract(member, str(self.install_dir))
                    # update every file — smooth bar (was throttled every 20 → jumpy)
                    if progress_cb:
                        pct = 12 + int(74 * (i + 1) / total)
                        progress_cb(pct, f"Extracting {Path(member).name[:40]}")

            if progress_cb:
                progress_cb(86, "Saving API key...")
            if self.api_key:
                cfg_dir = Path.home() / ".happy-photo-organizer"
                cfg_dir.mkdir(parents=True, exist_ok=True)
                cfg_file = cfg_dir / "auth.json"
                existing = {}
                if cfg_file.exists():
                    try:
                        existing = json.loads(cfg_file.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                existing.update({"api_key": self.api_key.strip()})
                if "model" not in existing:
                    existing["model"] = "gemini-3.1-flash-lite"
                cfg_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")

            # Shortcuts
            exe_path = self._find_exe()
            if exe_path:
                if self.create_desktop_shortcut:
                    if progress_cb:
                        progress_cb(89, "Creating Desktop shortcut...")
                    self._create_shortcut(
                        exe_path,
                        Path.home() / "Desktop" / f"{APP_NAME}.lnk",
                    )
                if self.create_start_menu:
                    if progress_cb:
                        progress_cb(93, "Adding to Start Menu...")
                    start_menu = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
                    start_menu.mkdir(parents=True, exist_ok=True)
                    self._create_shortcut(exe_path, start_menu / f"{APP_NAME}.lnk")

            # Create uninstaller + register in Windows Add/Remove Programs
            if progress_cb:
                progress_cb(96, "Setting up uninstaller...")
            uninst_bat = self._write_uninstaller()
            self._register_uninstall(exe_path, uninst_bat)

            if progress_cb:
                progress_cb(100, "Done!")
            return True, "Install complete"
        except Exception as e:
            return False, f"Install failed: {e}"

    def _write_uninstaller(self) -> Path:
        """Generate uninstall.bat in install_dir. Returns path."""
        assert self.install_dir is not None
        bat = self.install_dir / "uninstall.bat"
        install_dir_str = str(self.install_dir)
        bat.write_text(f"""@echo off
setlocal
echo.
echo  ==========================================
echo   Uninstall {APP_NAME}
echo  ==========================================
echo.
echo  Install location: {install_dir_str}
echo.
choice /C YN /N /M "  Continue? [Y/N] "
if errorlevel 2 (
    echo  Cancelled.
    timeout /t 2 /nobreak >nul
    exit /b
)
echo.
echo  Closing running app...
taskkill /F /IM {APP_EXE_NAME} >nul 2>&1
echo  Removing shortcuts...
del /Q "%USERPROFILE%\\Desktop\\{APP_NAME}.lnk" >nul 2>&1
del /Q "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\{APP_NAME}.lnk" >nul 2>&1
echo  Removing registry entry...
reg delete "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\HappyPhotoOrganizer" /f >nul 2>&1
echo.
choice /C YN /N /M "  Also remove your config (API key)? [Y/N] "
if errorlevel 2 goto skipcfg
rmdir /S /Q "%USERPROFILE%\\.happy-photo-organizer" >nul 2>&1
echo  Config removed.
:skipcfg
echo.
echo  Removing install folder...
REM Spawn detached cmd to delete this folder after we exit
(
echo @echo off
echo timeout /t 2 /nobreak ^>nul
echo rmdir /S /Q "{install_dir_str}"
echo del "%%~f0"
) > "%TEMP%\\hpo_finish.bat"
start "" /B cmd /c "%TEMP%\\hpo_finish.bat"
echo.
echo  Done. Bye!
timeout /t 2 /nobreak >nul
exit
""", encoding="utf-8")
        return bat

    def _register_uninstall(self, exe_path: Path | None, uninstaller: Path) -> None:
        """Register in HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall
        so 'Add/Remove Programs' lists this app."""
        try:
            import winreg
            assert self.install_dir is not None
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\HappyPhotoOrganizer"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as k:
                winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
                winreg.SetValueEx(k, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
                winreg.SetValueEx(k, "Publisher", 0, winreg.REG_SZ, "Nick (Happy AI Family)")
                winreg.SetValueEx(k, "InstallLocation", 0, winreg.REG_SZ, str(self.install_dir))
                winreg.SetValueEx(k, "UninstallString", 0, winreg.REG_SZ, f'cmd /c "{uninstaller}"')
                if exe_path:
                    icon = exe_path.parent / "_internal" / "assets" / "happy_icon.ico"
                    if not icon.exists():
                        icon = exe_path.parent / "assets" / "happy_icon.ico"
                    if icon.exists():
                        winreg.SetValueEx(k, "DisplayIcon", 0, winreg.REG_SZ, str(icon))
                    winreg.SetValueEx(k, "DisplayIcon", 0, winreg.REG_SZ, str(exe_path))
                winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)
        except Exception:
            pass

    def _find_exe(self) -> Path | None:
        """Locate HappyPhotoOrganizer.exe in install_dir (possibly nested)"""
        if not self.install_dir:
            return None
        for p in self.install_dir.rglob(APP_EXE_NAME):
            return p
        return None

    def _create_shortcut(self, target: Path, link: Path) -> None:
        """Create Windows .lnk via COM (pywin32) or fallback to .bat"""
        try:
            import pythoncom
            from win32com.client import Dispatch
            shell = Dispatch("WScript.Shell")
            sc = shell.CreateShortcut(str(link))
            sc.Targetpath = str(target)
            sc.WorkingDirectory = str(target.parent)
            ico = target.parent / "_internal" / "assets" / "happy_icon.ico"
            if not ico.exists():
                ico = target.parent / "assets" / "happy_icon.ico"
            if ico.exists():
                sc.IconLocation = str(ico)
            sc.Save()
        except Exception:
            # fallback — write .bat file
            bat = link.with_suffix(".bat")
            bat.write_text(
                f'@echo off\nstart "" "{target}"\n', encoding="utf-8",
            )

    def launch_app(self) -> None:
        exe = self._find_exe()
        if exe and exe.exists():
            try:
                os.startfile(str(exe))
            except Exception:
                pass


# ─── Main Setup Window ─────────────────────────────────────────


class SetupWindow(ctk.CTk):
    PHASE_SETUP = "setup"
    PHASE_INSTALLING = "installing"
    PHASE_DONE = "done"

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")

        self.title(f"{APP_NAME} Setup")
        self.geometry("720x560")
        self.minsize(640, 520)
        self.resizable(False, False)

        icon = get_asset("happy_icon.ico")
        if icon:
            try:
                self.iconbitmap(str(icon))
            except Exception:
                pass

        self.installer = Installer()
        self.installer.install_dir = DEFAULT_INSTALL_DIR

        # load mascot images (regular + small for navigation hints)
        self._mascot_pil = None
        mp = get_asset("mascot.png")
        if mp:
            try:
                self._mascot_pil = Image.open(mp).convert("RGBA")
            except Exception:
                pass

        # (mascot bounce dropped — pack layout doesn't play nice with place_configure)

        # background canvas
        self.bg = GradientBackground(self, width=720, height=560)
        self.bg.place(x=0, y=0, relwidth=1.0, relheight=1.0)

        # hero card (placed on top)
        self.card = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=14, border_width=1,
                                  border_color=COLOR_CARD_LIGHT)
        self.card.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.88, relheight=0.85)

        self._build_setup_phase()

        self.bg.start()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _make_mascot(self, size: int) -> ctk.CTkImage | None:
        if not self._mascot_pil:
            return None
        # pre-resize with LANCZOS — sharper than CTkImage's runtime scaler
        # (CTkImage was clipping the arm on downscale)
        resized = self._mascot_pil.resize((size, size), Image.LANCZOS)
        return ctk.CTkImage(
            light_image=resized, dark_image=resized,
            size=(size, size),
        )

    # ─── Phase: Setup ─────────────────────────────

    def _clear_card(self):
        for w in self.card.winfo_children():
            w.destroy()

    def _build_setup_phase(self):
        self._clear_card()
        # Use pack (top → bottom) — no overlap, predictable spacing

        # mascot (top, smaller for clearer render — large sizes blur the arms)
        mascot_img = self._make_mascot(86)
        if mascot_img:
            self._mascot_label = ctk.CTkLabel(self.card, image=mascot_img, text="")
            self._mascot_label.pack(pady=(20, 4))

        ctk.CTkLabel(
            self.card, text=f"Welcome to {APP_NAME}",
            font=("Segoe UI", 22, "bold"), text_color=COLOR_PRIMARY,
        ).pack(pady=(0, 2))

        ctk.CTkLabel(
            self.card, text="AI-powered photo organizer • Setup takes 30 seconds",
            font=("Segoe UI", 11), text_color=COLOR_MUTED,
        ).pack(pady=(0, 14))

        # Form (centered, max width)
        form = ctk.CTkFrame(self.card, fg_color="transparent")
        form.pack(fill="x", padx=40, pady=0)

        # Install location
        ctk.CTkLabel(form, text="Install location",
                     font=("Segoe UI", 11, "bold"), text_color=COLOR_TEXT,
                     anchor="w").pack(fill="x", pady=(0, 2))
        path_row = ctk.CTkFrame(form, fg_color="transparent")
        path_row.pack(fill="x", pady=(0, 10))
        self.path_var = ctk.StringVar(value=str(DEFAULT_INSTALL_DIR))
        self.path_entry = ctk.CTkEntry(path_row, textvariable=self.path_var, height=32)
        self.path_entry.pack(side="left", fill="x", expand=True)
        enable_paste(self.path_entry)
        ctk.CTkButton(
            path_row, text="Browse", width=80, height=32,
            fg_color=COLOR_CARD_LIGHT, hover_color="#475569",
            command=self._pick_dir,
        ).pack(side="left", padx=(6, 0))

        # API key
        ctk.CTkLabel(form, text="Gemini API key  (optional, you can set later)",
                     font=("Segoe UI", 11, "bold"), text_color=COLOR_TEXT,
                     anchor="w").pack(fill="x", pady=(0, 2))
        key_row = ctk.CTkFrame(form, fg_color="transparent")
        key_row.pack(fill="x", pady=(0, 10))
        self.key_var = ctk.StringVar()
        self.key_entry = ctk.CTkEntry(key_row, textvariable=self.key_var, height=32,
                                       show="•", placeholder_text="AIzaSy...")
        self.key_entry.pack(side="left", fill="x", expand=True)
        enable_paste(self.key_entry)
        ctk.CTkButton(
            key_row, text="Get free key", width=110, height=32,
            fg_color="transparent", border_color=COLOR_PRIMARY, border_width=1,
            text_color=COLOR_PRIMARY, hover_color=COLOR_CARD_LIGHT,
            command=lambda: webbrowser.open("https://aistudio.google.com/apikey"),
        ).pack(side="left", padx=(6, 0))

        # checkboxes
        opts = ctk.CTkFrame(form, fg_color="transparent")
        opts.pack(fill="x", pady=(2, 0))
        self.cb_desktop = ctk.CTkCheckBox(opts, text="Create Desktop shortcut")
        self.cb_desktop.select()
        self.cb_desktop.pack(anchor="w", pady=1)
        self.cb_startmenu = ctk.CTkCheckBox(opts, text="Add to Start Menu")
        self.cb_startmenu.select()
        self.cb_startmenu.pack(anchor="w", pady=1)
        self.cb_launch = ctk.CTkCheckBox(opts, text="Launch after install")
        self.cb_launch.select()
        self.cb_launch.pack(anchor="w", pady=1)

        # buttons (anchored at bottom via separate frame, side=bottom)
        btn_row = ctk.CTkFrame(self.card, fg_color="transparent")
        btn_row.pack(side="bottom", pady=(0, 18))
        ctk.CTkButton(
            btn_row, text="Cancel", width=120, height=40,
            fg_color=COLOR_CARD_LIGHT, hover_color="#475569",
            command=self._on_close,
        ).pack(side="left", padx=4)
        self.install_btn = ctk.CTkButton(
            btn_row, text="✨ Install", width=180, height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color=COLOR_PRIMARY, hover_color=COLOR_ACCENT,
            text_color="white",
            command=self._start_install,
        )
        self.install_btn.pack(side="left", padx=4)

    def _pick_dir(self):
        d = filedialog.askdirectory(title="Choose install folder", initialdir=str(Path.home()))
        if d:
            # append /HappyPhotoOrganizer if user picked plain folder
            chosen = Path(d)
            if chosen.name != "HappyPhotoOrganizer":
                chosen = chosen / "HappyPhotoOrganizer"
            self.path_var.set(str(chosen))

    def _start_install(self):
        target = self.path_var.get().strip()
        if not target:
            messagebox.showwarning("Path required", "Please choose an install location.")
            return
        self.installer.install_dir = Path(target)
        self.installer.api_key = self.key_var.get().strip()
        self.installer.create_desktop_shortcut = bool(self.cb_desktop.get())
        self.installer.create_start_menu = bool(self.cb_startmenu.get())
        self.installer.launch_after = bool(self.cb_launch.get())

        self._build_installing_phase()
        # delay thread start ~200ms so user sees 0% before extraction races ahead
        self.after(200, lambda: threading.Thread(target=self._install_worker, daemon=True).start())

    # ─── Phase: Installing ────────────────────────

    def _build_installing_phase(self):
        self._clear_card()

        # ─── Top: compact header — mascot left, progress right ─────
        top = ctk.CTkFrame(self.card, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(18, 10))

        mascot_img = self._make_mascot(56)
        if mascot_img:
            self._mascot_label = ctk.CTkLabel(top, image=mascot_img, text="")
            self._mascot_label.pack(side="left", padx=(0, 16))

        info = ctk.CTkFrame(top, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)

        # Title row with % on the right
        title_row = ctk.CTkFrame(info, fg_color="transparent")
        title_row.pack(fill="x")
        ctk.CTkLabel(
            title_row, text="Installing...",
            font=("Segoe UI", 18, "bold"), text_color=COLOR_PRIMARY,
        ).pack(side="left")
        self.install_pct = ctk.CTkLabel(
            title_row, text="0%",
            font=("Segoe UI", 16, "bold"), text_color=COLOR_TEXT,
        )
        self.install_pct.pack(side="right")

        self.install_status = ctk.CTkLabel(
            info, text="Starting...",
            font=("Segoe UI", 10), text_color=COLOR_MUTED, anchor="w",
        )
        self.install_status.pack(fill="x", pady=(2, 6))

        self.install_bar = ctk.CTkProgressBar(
            info, height=10, progress_color=COLOR_PRIMARY,
        )
        self.install_bar.pack(fill="x")
        self.install_bar.set(0)

        # ─── Divider ──────────────────────────────────────────────
        ctk.CTkFrame(self.card, height=1, fg_color=COLOR_CARD_LIGHT).pack(
            fill="x", padx=20, pady=(4, 8),
        )

        # ─── Body: License + Tips (scrollable, read-only) ─────────
        ctk.CTkLabel(
            self.card, text="📖 While we install — please read",
            font=("Segoe UI", 12, "bold"), text_color=COLOR_TEXT, anchor="w",
        ).pack(fill="x", padx=20, pady=(0, 4))

        text_box = ctk.CTkTextbox(
            self.card, fg_color="#0A1220", text_color="#CBD5E1",
            font=("Consolas", 10), corner_radius=6, wrap="word",
        )
        text_box.pack(fill="both", expand=True, padx=20, pady=(0, 18))
        text_box.insert("end", LICENSE_TEXT)
        text_box.configure(state="disabled")

        self.update_idletasks()

    def _install_worker(self):
        def cb(pct, msg):
            self.after(0, lambda: self._update_progress(pct, msg))
        ok, msg = self.installer.install(progress_cb=cb)
        self.after(0, lambda: self._on_install_done(ok, msg))

    def _update_progress(self, pct: int, msg: str):
        try:
            self.install_bar.set(pct / 100)
            self.install_pct.configure(text=f"{pct}%")
            self.install_status.configure(text=msg)
        except Exception:
            pass

    def _on_install_done(self, ok: bool, msg: str):
        if not ok:
            messagebox.showerror("Install failed", msg)
            self._build_setup_phase()
            return
        self._build_done_phase()
        if self.installer.launch_after:
            self.after(800, self._launch_and_close)

    # ─── Phase: Done ──────────────────────────────

    def _build_done_phase(self):
        self._clear_card()
        mascot_img = self._make_mascot(100)
        if mascot_img:
            self._mascot_label = ctk.CTkLabel(self.card, image=mascot_img, text="")
            self._mascot_label.pack(pady=(36, 12))

        ctk.CTkLabel(
            self.card, text="All Done! 🎉",
            font=("Segoe UI", 26, "bold"), text_color=COLOR_OK,
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            self.card, text=f"{APP_NAME} is ready to use",
            font=("Segoe UI", 13), text_color=COLOR_MUTED,
        ).pack(pady=(0, 12))

        ctk.CTkLabel(
            self.card,
            text=f"Installed to: {self.installer.install_dir}",
            font=("Segoe UI", 10), text_color=COLOR_MUTED,
            wraplength=560, justify="center",
        ).pack(pady=(0, 0))

        btn_row = ctk.CTkFrame(self.card, fg_color="transparent")
        btn_row.pack(side="bottom", pady=(0, 24))
        ctk.CTkButton(
            btn_row, text="Close", width=110, height=40,
            fg_color=COLOR_CARD_LIGHT, hover_color="#475569",
            command=self._on_close,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            btn_row, text="🚀 Launch now", width=180, height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color=COLOR_OK, hover_color="#0EA371",
            command=self._launch_and_close,
        ).pack(side="left", padx=4)

    def _launch_and_close(self):
        self.installer.launch_app()
        self._on_close()

    def _on_close(self):
        try:
            self.bg.stop()
        except Exception:
            pass
        self.destroy()


def _detect_existing_install_dir() -> Path | None:
    """Find a prior install location via Add/Remove Programs registry. Used by --upgrade."""
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\HappyPhotoOrganizer"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as k:
            loc, _ = winreg.QueryValueEx(k, "InstallLocation")
            p = Path(loc)
            if p.exists():
                return p
    except Exception:
        pass
    return None


def _run_silent_upgrade() -> int:
    """Headless install — used by app's auto-updater. No UI, reuse prior settings."""
    print(f"[silent-upgrade] {APP_NAME} v{APP_VERSION}")
    installer = Installer()
    installer.install_dir = _detect_existing_install_dir() or DEFAULT_INSTALL_DIR
    installer.api_key = ""  # preserved from prior config — installer.install() merges
    installer.create_desktop_shortcut = True
    installer.create_start_menu = True
    installer.launch_after = True
    print(f"[silent-upgrade] target dir: {installer.install_dir}")

    # Best-effort: stop a running instance so we can overwrite files
    try:
        import subprocess as _sp
        _sp.run(
            ["taskkill", "/F", "/IM", APP_EXE_NAME],
            stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, timeout=5,
        )
        time.sleep(0.5)
    except Exception:
        pass

    def _cb(pct: int, msg: str):
        print(f"[silent-upgrade] {pct:3d}%  {msg}")

    ok, msg = installer.install(progress_cb=_cb)
    if not ok:
        print(f"[silent-upgrade] FAILED: {msg}")
        return 1
    print(f"[silent-upgrade] OK — relaunching app")
    installer.launch_app()
    return 0


def main() -> int:
    args = sys.argv[1:]
    if "--silent" in args or "--upgrade" in args:
        return _run_silent_upgrade()
    app = SetupWindow()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
