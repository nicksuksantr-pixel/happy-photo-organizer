"""
tray.py — System-tray wrapper around pystray.Icon.

Runs detached on a daemon thread so the Tk mainloop stays in the main thread.
The `app` argument must expose three methods that get scheduled back onto the
Tk loop via `app.after(0, ...)`:
  - app._show_window_from_tray()
  - app._update_check_tick()
  - app._real_quit()
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

# pystray is optional — main.py guards the import so the app still runs
# even when the tray dependency fails to load.
try:
    import pystray
    from pystray import Menu as _TrayMenu, MenuItem as _TrayItem
except Exception:
    pystray = None  # type: ignore[assignment]
    _TrayMenu = None  # type: ignore[assignment]
    _TrayItem = None  # type: ignore[assignment]

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ICON_PATH = _PROJECT_ROOT / "assets" / "happy_icon.ico"


class HappyTray:
    """Wraps pystray.Icon with our app's menu (Show / Check update / Quit)."""

    def __init__(self, app):
        self.app = app
        self.icon = None
        self._image = self._load_icon_image()

    @staticmethod
    def _load_icon_image():
        try:
            return Image.open(_ICON_PATH)
        except Exception:
            return Image.new("RGBA", (32, 32), (251, 146, 60, 255))

    def start(self) -> bool:
        """Start the tray icon. Returns False if pystray is unavailable."""
        if pystray is None:
            return False
        self.icon = pystray.Icon(
            "HappyPhotoOrganizer",
            icon=self._image,
            title="Happy Photo Organizer",
            menu=_TrayMenu(
                _TrayItem("Show", self._on_show, default=True),
                _TrayItem("Check for updates now", self._on_check_update),
                _TrayMenu.SEPARATOR,
                _TrayItem("Quit", self._on_quit),
            ),
        )
        self.icon.run_detached()
        return True

    def stop(self) -> None:
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None

    # --- Menu callbacks (fire on pystray's thread → marshal to Tk via after) ---

    def _on_show(self, icon, item):
        try:
            self.app.after(0, self.app._show_window_from_tray)
        except Exception:
            pass

    def _on_check_update(self, icon, item):
        try:
            self.app.after(0, self.app._update_check_tick)
        except Exception:
            pass

    def _on_quit(self, icon, item):
        try:
            self.app.after(0, self.app._real_quit)
        except Exception:
            pass


__all__ = ["HappyTray", "pystray"]
