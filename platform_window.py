"""Cross-platform helpers for foreground window title + close."""

from __future__ import annotations

import platform
import subprocess
import sys
from typing import Callable

_active_title_fn: Callable[[], str] | None = None


def _title_darwin() -> str:
    script = r"""
tell application "System Events"
    set frontProc to first application process whose frontmost is true
    set winTitle to ""
    try
        set winTitle to name of window 1 of frontProc
    end try
    return winTitle
end tell
"""
    try:
        out = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return (out.stdout or "").strip().lower()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _title_win32() -> str:
    try:
        import pygetwindow as gw  # type: ignore

        w = gw.getActiveWindow()
        if w and w.title:
            return w.title.lower()
    except Exception:
        pass
    return ""


def _title_linux() -> str:
    try:
        out = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowname"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return (out.stdout or "").strip().lower()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def get_active_window_title() -> str:
    global _active_title_fn
    if _active_title_fn is None:
        system = platform.system()
        if system == "Darwin":
            _active_title_fn = _title_darwin
        elif system == "Windows":
            _active_title_fn = _title_win32
        else:
            _active_title_fn = _title_linux
    return _active_title_fn()


def try_close_foreground_window() -> bool:
    """Best-effort close of the current foreground window (tab/window)."""
    system = platform.system()
    if system == "Windows":
        try:
            import pygetwindow as gw  # type: ignore

            w = gw.getActiveWindow()
            if w:
                w.close()
                return True
        except Exception:
            return False
    if system == "Darwin":
        try:
            import pygetwindow as gw  # type: ignore

            w = gw.getActiveWindow()
            if w:
                w.close()
                return True
        except Exception:
            pass
        # Fallback: Cmd+W on macOS (closes tab in many browsers)
        try:
            script = r"""
tell application "System Events"
    keystroke "w" using command down
end tell
"""
            subprocess.run(["osascript", "-e", script], check=False, timeout=3)
            return True
        except (OSError, subprocess.TimeoutExpired):
            return False
    # Linux: try xdotool close
    try:
        subprocess.run(
            ["xdotool", "getactivewindow", "windowclose"],
            check=False,
            timeout=2,
        )
        return True
    except OSError:
        return False


def show_warning_popup(site: str) -> None:
    msg = f"You're on {site}.\nClose it now — Focus Klaxon is losing patience."
    system = platform.system()
    if system == "Windows":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, msg, "Focus Klaxon", 0x30)
        except Exception:
            print(msg)
    elif system == "Darwin":
        try:
            safe = msg.replace("\\", "\\\\").replace('"', '\\"')
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'display dialog "{safe}" buttons {{"OK"}} default button 1 '
                    f"with title \"Focus Klaxon\" with icon caution",
                ],
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            print(msg)
    else:
        try:
            subprocess.run(
                ["zenity", "--warning", "--text", msg],
                check=False,
                timeout=30,
            )
        except OSError:
            print(msg)


if __name__ == "__main__":  # quick manual test
    print(get_active_window_title())
