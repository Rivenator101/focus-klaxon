"""
Focus Klaxon watcher: detect distraction window titles, escalate warnings,
optional mouse chaos, then close foreground window and open work URL.
"""

from __future__ import annotations

import json
import random
import sys
import time
import webbrowser
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pyautogui
from colorama import Fore, Style, init as colorama_init

from logger import (
    count_recent_distractions,
    generate_report,
    log_distraction,
    personalized_haiku,
    session_start,
)
from platform_window import (
    get_active_context_text,
    show_info_popup,
    show_warning_popup,
    try_close_foreground_window,
)

colorama_init(autoreset=True)

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

pyautogui.FAILSAFE = True

Phase = Literal["idle", "warn", "mouse", "close"]


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise SystemExit(f"Missing {CONFIG_PATH}")
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"Config JSON corrupted: {e}")
    
    # Validate required fields
    required_fields = {
        "trigger_sites": list,
        "safe_windows": list,
        "work_url": str,
        "warning_seconds": (int, float),
        "grace_after_mouse_seconds": (int, float),
        "mouse_crazy_seconds": (int, float),
    }
    
    for field, expected_type in required_fields.items():
        if field not in cfg:
            raise SystemExit(f"Config missing required field: {field}")
        
        value = cfg[field]
        if isinstance(expected_type, tuple):
            if not isinstance(value, expected_type):
                raise SystemExit(f"Config '{field}' must be {expected_type}, got {type(value).__name__}")
        else:
            if not isinstance(value, expected_type):
                raise SystemExit(f"Config '{field}' must be {expected_type.__name__}, got {type(value).__name__}")
    
    return cfg


def match_trigger(context_lower: str, triggers: list[str]) -> str | None:
    for t in triggers:
        key = t.lower().strip()
        if key and key in context_lower:
            return t
    return None


def is_safe_window(context_lower: str, safe: list[str]) -> bool:
    for s in safe:
        key = s.lower().strip()
        if key and key in context_lower:
            return True
    return False


def still_on_trigger(site: str, triggers: list[str], safe: list[str]) -> bool:
    context = get_active_context_text()
    if not context or is_safe_window(context, safe):
        return False
    return match_trigger(context, triggers) == site


def wait_while_distraction(
    site: str,
    triggers: list[str],
    safe: list[str],
    total_seconds: float,
    poll: float = 0.25,
) -> bool:
    """Return True if still distracted after total_seconds."""
    deadline = time.monotonic() + total_seconds
    while time.monotonic() < deadline:
        if not still_on_trigger(site, triggers, safe):
            return False
        time.sleep(poll)
    return still_on_trigger(site, triggers, safe)


def mouse_go_crazy(duration_seconds: float) -> None:
    print(f"{Fore.YELLOW}   🐁 MOUSE PUNISHMENT INITIATED 🐁{Style.RESET_ALL}")
    screen_w, screen_h = pyautogui.size()
    start_x, start_y = pyautogui.position()
    deadline = time.monotonic() + max(0.5, duration_seconds)
    wave = 0
    while time.monotonic() < deadline:
        wave += 1
        intensity = 10 + (wave % 4) * 5
        for _ in range(10):
            pyautogui.moveRel(
                intensity * (1 if _ % 2 == 0 else -1),
                intensity * (1 if _ % 3 == 0 else -1),
                duration=0.02,
            )
        for _ in range(6):
            pyautogui.moveRel(
                random.randint(-intensity * 2, intensity * 2),
                random.randint(-intensity * 2, intensity * 2),
                duration=0.01,
            )
        if wave % 3 == 0:
            pyautogui.moveTo(10, 10, duration=0.08)
            pyautogui.moveTo(screen_w - 10, 10, duration=0.08)
            pyautogui.moveTo(screen_w - 10, screen_h - 10, duration=0.08)
            pyautogui.moveTo(10, screen_h - 10, duration=0.08)

    pyautogui.moveTo(start_x, start_y, duration=0.25)
    print(f"{Fore.GREEN}   🐁 Mouse restored. Behave.{Style.RESET_ALL}")


def build_dashboard_url(work_url: str, site: str, phases: list[str]) -> str:
    """
    Add auto-log payload for dashboard so it can store events on load.
    Keeps existing query params.
    """
    parsed = urlparse(work_url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    params["fk_site"] = site
    params["fk_phases"] = ",".join(phases)
    params["fk_ts"] = str(int(time.time()))
    if "mouse" in phases or "auto_close" in phases:
        params["fk_glitch"] = "1"
    query = urlencode(params)
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment)
    )


def trigger_repeat_nudge(nudge_url: str, site: str, per_hour_count: int) -> None:
    """
    Opens a nudge URL and types a warning message if possible.
    Works best when nudge_url is a Google Doc that's already editable.
    """
    msg = (
        f"Focus check: return to work now. "
        f"You got distracted {per_hour_count} times in the past hour ({site})."
    )
    show_info_popup("Focus Klaxon", "Repeat distraction detected. Launching nudge mode.")
    try:
        if not nudge_url or not nudge_url.strip():
            print(f"{Fore.YELLOW}⚠️  Nudge URL not configured{Style.RESET_ALL}", file=sys.stderr)
            return
        webbrowser.open(nudge_url)
        time.sleep(1.8)
        # This types into whichever field has focus.
        pyautogui.typewrite(msg, interval=0.01)
        pyautogui.press("enter")
    except (OSError, pyautogui.FailSafeException) as e:
        print(f"{Fore.YELLOW}⚠️  Nudge mode failed: {e}{Style.RESET_ALL}", file=sys.stderr)
    except Exception as e:
        print(f"{Fore.YELLOW}⚠️  Unexpected error in nudge mode: {e}{Style.RESET_ALL}", file=sys.stderr)


def run_watcher() -> None:
    cfg = load_config()
    triggers = cfg.get("trigger_sites", [])
    safe = cfg.get("safe_windows", [])
    work_url = cfg.get("work_url", "about:blank")
    if not work_url or not work_url.strip():
        work_url = "about:blank"
    
    warn_s = float(cfg.get("warning_seconds", 5))
    grace_s = float(cfg.get("grace_after_mouse_seconds", 4))
    mouse_on = bool(cfg.get("mouse_crazy_enabled", True))
    mouse_s = float(cfg.get("mouse_crazy_seconds", 12))
    # Cap mouse duration to prevent user self-trap
    mouse_s = min(max(mouse_s, 1), 60)
    
    nudge_on = bool(cfg.get("repeat_nudge_enabled", True))
    nudge_url = str(cfg.get("repeat_nudge_url", work_url))
    nudge_min = int(cfg.get("repeat_nudge_min_per_hour", 2))

    session_start()

    print("=" * 58)
    print(f"{Fore.CYAN}🔨 FOCUS KLAXON — The Enforcer 🔨{Style.RESET_ALL}")
    print("=" * 58)
    print(f"Watching titles for: {', '.join(triggers)}")
    print(f"Work / focus URL: {work_url}")
    print(f"1) Popup + {warn_s:.0f}s to comply")
    print(f"2) Mouse chaos for {mouse_s:.0f}s (if still distracted)")
    print("3) Close foreground + open focus URL")
    print(f"{Fore.YELLOW}Ctrl+C{Style.RESET_ALL} stops watcher and prints a report.\n")

    phase: Phase = "idle"
    active_site: str | None = None

    try:
        while True:
            context = get_active_context_text()

            if phase == "idle":
                if not context or is_safe_window(context, safe):
                    time.sleep(0.6)
                    continue
                site = match_trigger(context, triggers)
                if not site:
                    time.sleep(0.6)
                    continue
                active_site = site
                phase = "warn"
                print(f"\n{Fore.RED}\a⚠️  [{site}] detected in active browser context.{Style.RESET_ALL}")
                print(f"   You have ~{warn_s:.0f}s. Close it or switch away.")
                show_warning_popup(site)
                continue

            # Escalation phases for active_site
            assert active_site is not None

            if not still_on_trigger(active_site, triggers, safe):
                print(f"{Fore.GREEN}   Focus Klaxon stands down.{Style.RESET_ALL}")
                phase = "idle"
                active_site = None
                time.sleep(0.5)
                continue

            if phase == "warn":
                if wait_while_distraction(active_site, triggers, safe, warn_s):
                    log_distraction(active_site, note="warn_popup")
                    phase = "mouse"
                    recent_count = count_recent_distractions(1)
                    if nudge_on and recent_count >= nudge_min:
                        trigger_repeat_nudge(nudge_url, active_site, recent_count)
                    if mouse_on:
                        print(f"\n{Fore.RED}   Still there? Mouse chaos.{Style.RESET_ALL}")
                        show_info_popup("Focus Klaxon", "Mouse of Doom: Activated")
                        mouse_go_crazy(mouse_s)
                        log_distraction(active_site, note="mouse_chaos")
                    else:
                        print(
                            f"\n{Fore.YELLOW}   Mouse chaos disabled — final grace: {grace_s:.0f}s.{Style.RESET_ALL}"
                        )
                else:
                    phase = "idle"
                    active_site = None
                continue

            if phase == "mouse":
                if wait_while_distraction(active_site, triggers, safe, grace_s):
                    phase = "close"
                else:
                    print(f"{Fore.GREEN}   You escaped. Barely.{Style.RESET_ALL}")
                    phase = "idle"
                    active_site = None
                continue

            if phase == "close":
                print(f"\n{Fore.RED}💀 Closing foreground window. Opening focus URL.{Style.RESET_ALL}")
                show_info_popup("Focus Klaxon", "Final step: closing distraction tab now")
                log_distraction(active_site, note="auto_close")
                closed = try_close_foreground_window()
                if not closed:
                    print("   (Close may have failed — browser security varies.)")
                try:
                    phases = ["warn", "auto_close"] if not mouse_on else ["warn", "mouse", "auto_close"]
                    dashboard_url = build_dashboard_url(work_url, active_site, phases)
                    webbrowser.open(dashboard_url)
                except (OSError, ValueError) as e:
                    print(f"{Fore.YELLOW}⚠️  Could not open dashboard: {e}{Style.RESET_ALL}", file=sys.stderr)
                print(f"\n{Fore.MAGENTA}{personalized_haiku(active_site, 'auto_close')}{Style.RESET_ALL}\n")
                phase = "idle"
                active_site = None
                time.sleep(1.5)
                continue

    except KeyboardInterrupt:
        print(f"\n{Fore.CYAN}📊 Watcher stopping — generating report…{Style.RESET_ALL}")
        generate_report()
    except Exception as e:
        print(f"\n{Fore.RED}❌ Fatal error in watcher: {e}{Style.RESET_ALL}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run_watcher()
    sys.exit(0)
