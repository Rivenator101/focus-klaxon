"""Shame log + session reports for Focus Klaxon."""

from __future__ import annotations

import json
import os
import random
from datetime import date, datetime
from pathlib import Path

from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)

DATA_DIR = Path(__file__).resolve().parent
LOG_FILE = DATA_DIR / "distractions.json"
SESSION_FILE = DATA_DIR / "session_state.json"

HAIKUS = [
    "Fingers drift to memes\nThe deadline watches in silence\nClose Discord, coward.",
    "Another tab opens\nYour future self sends regards\nThey are so tired.",
    "Focus was right here\nYou traded it for pixels\nThe klaxon remembers.",
    "The mouse runs in fear\nTabs scatter like autumn leaves\nWork still waits, patient.",
]


def _init_log() -> None:
    if not LOG_FILE.exists():
        LOG_FILE.write_text("[]", encoding="utf-8")


def log_distraction(site_name: str, note: str | None = None) -> None:
    _init_log()
    data = json.loads(LOG_FILE.read_text(encoding="utf-8"))
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "site": site_name,
        "session_id": date.today().isoformat(),
        "note": note,
    }
    data.append(entry)
    LOG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"{Fore.RED}⚠️  Logged distraction:{Style.RESET_ALL} {site_name}")


def get_logs_for_day(day: date) -> list[dict]:
    _init_log()
    data = json.loads(LOG_FILE.read_text(encoding="utf-8"))
    key = day.isoformat()
    return [d for d in data if d.get("session_id") == key]


def random_haiku() -> str:
    return random.choice(HAIKUS)


def _count_by_site(entries: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for e in entries:
        s = e.get("site", "unknown")
        out[s] = out.get(s, 0) + 1
    return out


def get_improvement_message(today_count: int) -> str:
    yesterday = date.today().toordinal() - 1
    y_date = date.fromordinal(yesterday)
    y_logs = get_logs_for_day(y_date)
    y_count = len(y_logs)
    if y_count == 0 and today_count == 0:
        return "Clean slate. Suspiciously clean."
    if y_count == 0:
        return f"First comparable day — today: {today_count} slip(s)."
    delta = y_count - today_count
    pct = round(100.0 * delta / max(y_count, 1))
    if delta > 0:
        return f"+{pct}% vs yesterday ({y_count} → {today_count})."
    if delta < 0:
        return f"{pct}% vs yesterday ({y_count} → {today_count}). Ouch."
    return "Flat vs yesterday. Consistency is a choice."


def generate_report() -> None:
    today_logs = get_logs_for_day(date.today())
    n = len(today_logs)
    by_site = _count_by_site(today_logs)
    top = max(by_site.items(), key=lambda x: x[1])[0] if by_site else "none"

    focus_est = max(0, 60 - n * 5)

    print("\n" + "=" * 50)
    print(f"{Fore.CYAN}📊 SESSION REPORT (today){Style.RESET_ALL}")
    print("=" * 50)
    print(f"Focus time (rough est.): {focus_est} min")
    print(f"Distractions logged: {n}")
    print(f"Top trigger: {top}")
    print(f"Trend: {get_improvement_message(n)}")
    if n >= 3:
        print(f"\n{Fore.MAGENTA}{random_haiku()}{Style.RESET_ALL}")
    print("=" * 50 + "\n")


def session_start() -> None:
    payload = {"started_at": datetime.now().isoformat(timespec="seconds")}
    SESSION_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def session_touch_focus_minutes(add_minutes: int) -> None:
    """Bribe-the-ghost: add imaginary focus credit for demo laughs."""
    state = {}
    if SESSION_FILE.exists():
        state = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    credit = int(state.get("focus_credit_minutes", 0)) + add_minutes
    state["focus_credit_minutes"] = credit
    SESSION_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def print_recent_logs(limit: int = 10) -> None:
    _init_log()
    data = json.loads(LOG_FILE.read_text(encoding="utf-8"))
    if not data:
        print(f"{Fore.GREEN}✨ No distractions logged. Beautiful lie or truth?{Style.RESET_ALL}")
        return
    print(f"\n{Fore.YELLOW}Last {limit} events:{Style.RESET_ALL}")
    for row in data[-limit:]:
        print(f"  {row.get('timestamp')} — {row.get('site')}")
