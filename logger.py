"""Shame log + session reports for Focus Klaxon."""

from __future__ import annotations

import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)

DATA_DIR = Path(__file__).resolve().parent
LOG_FILE = DATA_DIR / "distractions.json"
SESSION_FILE = DATA_DIR / "session_state.json"

GENERAL_HAIKUS = [
    "A tab blooms open\nThe task list waits by the door\nCome back to your work.",
    "Small drift in attention\nMinutes pool without a sound\nChoose what matters now.",
    "The cursor is still\nA page asks for one more scroll\nYour draft waits for you.",
]

SITE_HAIKUS = {
    "chess": [
        "Quiet opening line\nYour deadline studies endgames\nReturn to the board.",
        "Knights cross midnight squares\nA project clock keeps moving\nMake the next move count.",
    ],
    "discord": [
        "Soft pings in the dark\nYour unfinished thought is near\nProtect the next hour.",
        "Voices fill the room\nYour own page is still blank here\nWrite one steady line.",
    ],
    "youtube": [
        "One video rolls\nThen another, then another\nClose the loop, begin.",
    ],
    "reddit": [
        "Thread after thread turns\nThe work you meant to finish\nWaits in another tab.",
    ],
    "social": [
        "A feed keeps moving\nYour real life moves more slowly\nPick the lasting thing.",
    ],
}


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


def count_recent_distractions(hours: int = 1) -> int:
    """Count distraction incidents in the recent rolling window."""
    _init_log()
    data = json.loads(LOG_FILE.read_text(encoding="utf-8"))
    cutoff = datetime.now() - timedelta(hours=hours)
    count = 0
    for row in data:
        ts = row.get("timestamp")
        note = row.get("note")
        if not ts or note != "warn_popup":
            continue
        try:
            dt = datetime.fromisoformat(str(ts))
        except ValueError:
            continue
        if dt >= cutoff:
            count += 1
    return count


def _site_bucket(site: str) -> str:
    s = site.lower()
    if "chess" in s:
        return "chess"
    if "discord" in s:
        return "discord"
    if "youtube" in s:
        return "youtube"
    if "reddit" in s:
        return "reddit"
    if any(x in s for x in ["twitter", "x.com", "tiktok", "instagram", "facebook"]):
        return "social"
    return "general"


def _time_line(hour: int) -> str:
    if hour < 6:
        return "Late night window light"
    if hour < 12:
        return "Morning air is clear"
    if hour < 18:
        return "Afternoon mind drift"
    return "Evening focus thins"


def _phase_line(note: str | None) -> str:
    if note == "warn_popup":
        return "A quiet warning lands"
    if note == "mouse_chaos":
        return "The cursor starts to dance"
    if note == "auto_close":
        return "The tab closes itself"
    return "A small detour appears"


def personalized_haiku(site: str, note: str | None = None) -> str:
    """Create a context-aware haiku from site + phase + repetition + time."""
    now = datetime.now()
    today_entries = get_logs_for_day(date.today())
    site_count = sum(1 for e in today_entries if str(e.get("site", "")).lower() == site.lower())
    repeat_line = (
        "First slip today"
        if site_count <= 1
        else f"{site_count}th return to {site}"
    )
    bucket = _site_bucket(site)
    pool = SITE_HAIKUS.get(bucket, GENERAL_HAIKUS)
    base = random.choice(pool)
    custom = f"{_time_line(now.hour)}\n{_phase_line(note)}\n{repeat_line}"
    # Keep most lines poetic; use context-aware version occasionally for personalization.
    return custom if random.random() < 0.35 else base


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
        print(f"\n{Fore.MAGENTA}{personalized_haiku(top, 'auto_close')}{Style.RESET_ALL}")
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
