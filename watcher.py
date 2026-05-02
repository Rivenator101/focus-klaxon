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

import pyautogui
from colorama import Fore, Style, init as colorama_init

from logger import generate_report, log_distraction, random_haiku, session_start
from platform_window import get_active_context_text, show_warning_popup, try_close_foreground_window

colorama_init(autoreset=True)

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

pyautogui.FAILSAFE = False

Phase = Literal["idle", "warn", "mouse", "close"]


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise SystemExit(f"Missing {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def match_trigger(context_lower: str, triggers: list[str]) -> str | None:
    for t in triggers:
        key = t.lower().strip()
        if key and key in context_lower:
            return t
    return None


def is_safe_window(context_lower: str, safe: list[str]) -> bool:
    for s in safe:
        if s.lower().strip() and s.lower().strip() in context_lower:
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


def mouse_go_crazy() -> None:
    print(f"{Fore.YELLOW}   🐁 MOUSE PUNISHMENT INITIATED 🐁{Style.RESET_ALL}")
    screen_w, screen_h = pyautogui.size()
    start_x, start_y = pyautogui.position()

    for wave in range(3):
        for _ in range(20):
            pyautogui.moveRel(
                (wave + 1) * 12 * (1 if _ % 2 == 0 else -1),
                (wave + 1) * 12 * (1 if _ % 3 == 0 else -1),
                duration=0.02,
            )
        for _ in range(10):
            pyautogui.moveRel(
                random.randint(-35, 35),
                random.randint(-35, 35),
                duration=0.01,
            )
        if wave == 1:
            pyautogui.moveTo(10, 10, duration=0.15)
            pyautogui.moveTo(screen_w - 10, 10, duration=0.15)
            pyautogui.moveTo(screen_w - 10, screen_h - 10, duration=0.15)
            pyautogui.moveTo(10, screen_h - 10, duration=0.15)

    pyautogui.moveTo(start_x, start_y, duration=0.25)
    print(f"{Fore.GREEN}   🐁 Mouse restored. Behave.{Style.RESET_ALL}")


def run_watcher() -> None:
    cfg = load_config()
    triggers = cfg.get("trigger_sites", [])
    safe = cfg.get("safe_windows", [])
    work_url = cfg.get("work_url", "about:blank")
    warn_s = float(cfg.get("warning_seconds", 5))
    grace_s = float(cfg.get("grace_after_mouse_seconds", 4))
    mouse_on = bool(cfg.get("mouse_crazy_enabled", True))

    session_start()

    print("=" * 58)
    print(f"{Fore.CYAN}🔨 FOCUS KLAXON — The Enforcer 🔨{Style.RESET_ALL}")
    print("=" * 58)
    print(f"Watching titles for: {', '.join(triggers)}")
    print(f"Work / focus URL: {work_url}")
    print(f"1) Popup + {warn_s:.0f}s to comply")
    print("2) Mouse chaos (if still distracted)")
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
                    phase = "mouse"
                    if mouse_on:
                        print(f"\n{Fore.RED}   Still there? Mouse chaos.{Style.RESET_ALL}")
                        mouse_go_crazy()
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
                log_distraction(active_site, note="auto_close")
                closed = try_close_foreground_window()
                if not closed:
                    print("   (Close may have failed — browser security varies.)")
                try:
                    webbrowser.open(work_url)
                except Exception:
                    pass
                print(f"\n{Fore.MAGENTA}{random_haiku()}{Style.RESET_ALL}\n")
                phase = "idle"
                active_site = None
                time.sleep(1.5)
                continue

    except KeyboardInterrupt:
        print(f"\n{Fore.CYAN}📊 Watcher stopping — generating report…{Style.RESET_ALL}")
        generate_report()


if __name__ == "__main__":
    run_watcher()
    sys.exit(0)
