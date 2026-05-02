#!/usr/bin/env python3
"""Focus Klaxon — CLI menu + watcher launcher."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import webbrowser
from pathlib import Path

from colorama import Fore, Style, init as colorama_init

from logger import (
    generate_report,
    personalized_haiku,
    print_recent_logs,
    session_touch_focus_minutes,
)

colorama_init(autoreset=True)

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        default = {
            "trigger_sites": ["chess.com", "discord", "reddit.com", "youtube.com"],
            "work_url": "about:blank",
            "safe_windows": ["cursor", "code", "terminal", "vscode", "iterm"],
            "warning_seconds": 5,
            "grace_after_mouse_seconds": 4,
            "mouse_crazy_enabled": True,
        }
        CONFIG_PATH.write_text(json.dumps(default, indent=2), encoding="utf-8")
        return default
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def add_trigger_site() -> None:
    site = input("Site substring to watch (e.g. chess.com): ").strip()
    if not site:
        print("Empty input — cancelled.")
        return
    cfg = load_config()
    sites: list[str] = cfg.setdefault("trigger_sites", [])
    if site not in sites:
        sites.append(site)
    save_config(cfg)
    print(f"{Fore.GREEN}✅ Added:{Style.RESET_ALL} {site}")


def set_work_url() -> None:
    url = input("Focus / work URL (dashboard or doc): ").strip()
    if not url:
        print("Empty input — cancelled.")
        return
    cfg = load_config()
    cfg["work_url"] = url
    save_config(cfg)
    print(f"{Fore.GREEN}✅ work_url set.{Style.RESET_ALL}")


def open_local_dashboard() -> None:
    docs_idx = ROOT / "docs" / "index.html"
    legacy_idx = ROOT / "dashboard" / "index.html"
    if docs_idx.exists():
        webbrowser.open(docs_idx.as_uri())
        return
    if legacy_idx.exists():
        webbrowser.open(legacy_idx.as_uri())
        return
    print(f"{Fore.YELLOW}No docs/index.html yet.{Style.RESET_ALL}")


def start_watcher_subprocess() -> None:
    watcher = ROOT / "watcher.py"
    print(f"\n{Fore.CYAN}Launching watcher (Ctrl+C there ends session + report).{Style.RESET_ALL}\n")
    subprocess.run([sys.executable, str(watcher)], check=False)


def pause_escape_hatch() -> None:
    phrase = input('Type exactly: i am weak\n> ').strip()
    if phrase == "i am weak":
        print(f"{Fore.YELLOW}Monitoring not running in menu mode — start watcher when ready.{Style.RESET_ALL}")
        print("You admitted weakness with honor. The klaxon will remember.")
    else:
        print(f"{Fore.RED}Escape denied.{Style.RESET_ALL}")


def bribe_ghost() -> None:
    session_touch_focus_minutes(10)
    print(
        f"{Fore.GREEN}🎺 +10 imaginary focus minutes.\n"
        f"{personalized_haiku('focus', 'warn_popup')}{Style.RESET_ALL}"
    )
    try:
        print("\a", end="")
    except Exception:
        pass


def menu_loop() -> None:
    while True:
        print("\n" + "🔨" * 18)
        print(f"    {Fore.CYAN}FOCUS KLAXON{Style.RESET_ALL} — productivity parasite")
        print("🔨" * 18)
        print("[1] Add trigger site")
        print("[2] View shame log (last 10)")
        print("[3] Set work / focus URL")
        print("[4] Open focus dashboard preview (docs/index.html)")
        print("[5] Start watcher (monitoring)")
        print("[6] Session report (today)")
        print("[7] Bribe the ghost (+10 focus min, fanfare bell)")
        print('[8] Escape hatch (type "i am weak")')
        print("[9] Exit")
        choice = input("\n> ").strip()

        if choice == "1":
            add_trigger_site()
        elif choice == "2":
            print_recent_logs(10)
        elif choice == "3":
            set_work_url()
        elif choice == "4":
            open_local_dashboard()
        elif choice == "5":
            start_watcher_subprocess()
        elif choice == "6":
            generate_report()
        elif choice == "7":
            bribe_ghost()
        elif choice == "8":
            pause_escape_hatch()
        elif choice == "9":
            print("👋 The klaxon never sleeps. You do.")
            break
        else:
            print(f"{Fore.YELLOW}Unknown option.{Style.RESET_ALL}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Focus Klaxon — CLI focus enforcer")
    parser.add_argument("--menu", action="store_true", help="Interactive menu (default if no other flags)")
    parser.add_argument("--report", action="store_true", help="Print today's session report")
    args = parser.parse_args()

    if args.report:
        generate_report()
        return

    if len(sys.argv) == 1:
        menu_loop()
        return

    if args.menu:
        menu_loop()
        return

    parser.print_help()


if __name__ == "__main__":
    main()
