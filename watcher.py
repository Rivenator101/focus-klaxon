"""
Focus Klaxon watcher: detect distraction window titles, escalate warnings,
optional mouse chaos, then close foreground window and open work URL.
"""

from __future__ import annotations

import json
import random
import re
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

pyautogui.FAILSAFE = False

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
    """Match triggers with word boundary awareness to reduce false positives."""
    for t in triggers:
        key = t.lower().strip()
        if not key:
            continue
        # Escape special regex characters and match as whole word or URL component
        escaped = re.escape(key)
        # Match: whole word boundary OR URL domain-like pattern (e.g., ".discord.com")
        if re.search(rf"\b{escaped}\b|\b\w*\.{escaped}(\b|\.)", context_lower):
            return t
    return None


def is_safe_window(context_lower: str, safe: list[str]) -> bool:
    """Check if context matches any safe window pattern with word boundaries."""
    for s in safe:
        pattern = s.strip()
        if not pattern:
            continue
        # For exact app names, use word boundary; for URL fragments, use substring
        escaped = re.escape(pattern.lower())
        if re.search(rf"\b{escaped}\b", context_lower):
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


def mouse_go_crazy(duration_seconds: float, intensity_level: int = 1) -> None:
    """Make mouse go berserk. intensity_level: 1=normal, 2=aggressive, 3=NUCLEAR"""
    print(f"{Fore.YELLOW}   🐁 MOUSE PUNISHMENT INITIATED 🐁{Style.RESET_ALL}")
    screen_w, screen_h = pyautogui.size()
    start_x, start_y = pyautogui.position()
    deadline = time.monotonic() + max(0.5, duration_seconds)
    wave = 0
    
    intensity_multiplier = [1, 1.5, 2.5][min(intensity_level - 1, 2)]
    move_delay = [0.02, 0.01, 0.005][min(intensity_level - 1, 2)]
    random_move_delay = [0.01, 0.005, 0.002][min(intensity_level - 1, 2)]
    
    while time.monotonic() < deadline:
        wave += 1
        intensity = int((10 + (wave % 4) * 5) * intensity_multiplier)
        
        # Straight line chaos
        for _ in range(10):
            pyautogui.moveRel(
                intensity * (1 if _ % 2 == 0 else -1),
                intensity * (1 if _ % 3 == 0 else -1),
                duration=move_delay,
            )
        
        # Random chaos
        random_iterations = [6, 12, 20][min(intensity_level - 1, 2)]
        for _ in range(random_iterations):
            pyautogui.moveRel(
                random.randint(-intensity * 2, intensity * 2),
                random.randint(-intensity * 2, intensity * 2),
                duration=random_move_delay,
            )
        
        # Corner bouncing (every 3 waves)
        if wave % 3 == 0:
            pyautogui.moveTo(10, 10, duration=0.08)
            pyautogui.moveTo(screen_w - 10, 10, duration=0.08)
            pyautogui.moveTo(screen_w - 10, screen_h - 10, duration=0.08)
            pyautogui.moveTo(10, screen_h - 10, duration=0.08)
        
        # NUCLEAR: click things randomly to close dialogs
        if intensity_level >= 3 and wave % 5 == 0:
            try:
                pyautogui.click(random.randint(100, screen_w - 100), random.randint(100, screen_h - 100))
            except Exception:
                pass

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


def trigger_repeat_nudge(nudge_url: str, site: str, per_hour_count: int, hijack_mode: bool = False) -> None:
    """
    Opens a nudge URL and types an aggressive warning message.
    If hijack_mode=True, adds keyboard smashing and extra aggression.
    """
    if per_hour_count >= 3:
        # NUCLEAR MODE: User is a repeat offender
        threats = [
            f"GET BACK TO YOUR FUCKING WORK NOW. You got distracted {per_hour_count} times in the past hour, you absolute unit.",
            f"BRRRRR. {per_hour_count} times??? {per_hour_count} TIMES?! Return to focus immediately.",
            f"Listen. You've been here {per_hour_count} times in one hour. This is unhinged behavior. Back. To. Work.",
            f"CRIMINAL ACTIVITY DETECTED. Distraction streak: {per_hour_count} in 60 minutes. STOP.",
        ]
        msg = random.choice(threats)
        popup_msg = f"REPEAT OFFENDER ALERT: {per_hour_count} distractions in 1 hour. Launching aggressive nudge."
    else:
        msg = (
            f"Focus check: you got distracted {per_hour_count} time{'s' if per_hour_count != 1 else ''} "
            f"in the past hour. Get back to {site} if you must, but open the work doc first."
        )
        popup_msg = f"Distraction detected ({per_hour_count}x/hr). Opening nudge doc..."
    
    show_info_popup("Focus Klaxon", popup_msg)
    try:
        if not nudge_url or not nudge_url.strip():
            print(f"{Fore.YELLOW}⚠️  Nudge URL not configured{Style.RESET_ALL}", file=sys.stderr)
            return
        webbrowser.open(nudge_url)
        time.sleep(2.0)
        
        # Type the threat message
        pyautogui.typewrite(msg, interval=0.01)
        pyautogui.press("enter")
        
        # If nuclear mode, add keyboard smashing for dramatic effect
        if hijack_mode and per_hour_count >= 3:
            time.sleep(0.5)
            print(f"{Fore.RED}   💀 KEYBOARD SMASH INCOMING 💀{Style.RESET_ALL}")
            smash_chars = "!@#$%^&*()" * 2
            for char in smash_chars:
                pyautogui.typewrite(char, interval=0.02)
            pyautogui.press("enter")
            pyautogui.typewrite("NOW FOCUS.", interval=0.03)
            time.sleep(0.3)
            
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
    repeat_violations: dict[str, int] = {}  # Track repeat offenders
    last_distraction_time: dict[str, float] = {}  # Track when we last caught each site

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
                
                # Check if this is a REPEAT OFFENSE (caught within 30 seconds of leaving)
                now = time.time()
                if site in last_distraction_time and (now - last_distraction_time[site]) < 30:
                    repeat_violations[site] = repeat_violations.get(site, 0) + 1
                    recent_count = count_recent_distractions(1)
                    
                    if recent_count >= nudge_min and nudge_on:
                        print(f"\n{Fore.RED}🚨 REPEAT OFFENSE! You returned to {site}! 🚨{Style.RESET_ALL}")
                        print(f"   Escalating to NUCLEAR nudge mode...")
                        trigger_repeat_nudge(nudge_url, site, recent_count, hijack_mode=True)
                        time.sleep(1.0)
                
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
                        # Use higher intensity if this is a repeat offender
                        intensity = 1
                        if active_site in repeat_violations and repeat_violations[active_site] >= 2:
                            intensity = 3
                            print(f"\n{Fore.RED}   REPEAT OFFENDER MODE: MAXIMUM MOUSE CHAOS{Style.RESET_ALL}")
                        elif recent_count >= 3:
                            intensity = 2
                            print(f"\n{Fore.RED}   Still there? Mouse chaos (AGGRESSIVE).{Style.RESET_ALL}")
                        else:
                            print(f"\n{Fore.RED}   Still there? Mouse chaos.{Style.RESET_ALL}")
                        
                        show_info_popup("Focus Klaxon", "Mouse of Doom: Activated")
                        mouse_go_crazy(mouse_s, intensity_level=intensity)
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
                # Track when we last caught this site (for repeat offense detection)
                if active_site:
                    last_distraction_time[active_site] = time.time()
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
