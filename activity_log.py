"""Structured local activity logging for the AI Email Agent.

The activity log is intentionally metadata-only. Do not write email bodies,
tokens, API keys, passwords, or PINs here.
"""
from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
ACTIVITY_FILE = LOG_DIR / "activity.jsonl"
MAX_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 5

_logger = logging.getLogger("activity")
_configured = False

SECRET_KEYS = {
    "pin",
    "pin_code",
    "pin_hash",
    "password",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "client_secret",
    "authorization",
    "body",
    "original_body",
    "ai_reply",
}


def _configure() -> None:
    global _configured
    if _configured:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        ACTIVITY_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.setLevel(logging.INFO)
    _logger.addHandler(handler)
    _logger.propagate = False
    _configured = True


def _safe(value):
    if isinstance(value, dict):
        return {
            str(key): ("[redacted]" if str(key).lower() in SECRET_KEYS else _safe(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_safe(item) for item in value[:50]]
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:500]


def log_activity(event: str, **details) -> None:
    """Append one safe JSON event to the local rotating activity log."""
    try:
        _configure()
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": str(event),
            "details": _safe(details),
        }
        _logger.info(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    except Exception:
        # Activity logging must never break email processing or dashboard actions.
        pass


def recent_activity(limit: int = 100) -> list[dict]:
    """Return recent activity events newest-first."""
    _configure()
    if not ACTIVITY_FILE.exists():
        return []
    lines = ACTIVITY_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    events = []
    for line in reversed(lines[-max(1, min(limit, 500)):]):
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events
