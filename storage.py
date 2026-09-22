"""Atomic JSON persistence and a shared lock for worker/dashboard updates."""
import json
import os
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

_lock = threading.RLock()


def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else ({} if default is None else default)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def draft_transaction(path):
    with _lock:
        lock_path = Path(path).with_suffix(".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "a+b") as handle:
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b"1")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                deadline = time.monotonic() + 120
                while True:
                    try:
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise TimeoutError("Draft storage is busy; please retry")
                        time.sleep(.05)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                handle.seek(0)
                if os.name == "nt":
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def is_demo(draft):
    return bool(draft.get("is_demo") or str(draft.get("email_id", "")).startswith("mock_"))


def get_retry_queue(path="data/retry_queue.json"):
    return read_json(path, default=[])


def save_retry_queue(queue, path="data/retry_queue.json"):
    write_json(path, queue)


def get_style_memory(path="data/style_memory.json"):
    return read_json(path, default={"edits": [], "patterns": []})


def save_style_memory(memory, path="data/style_memory.json"):
    write_json(path, memory)


def snooze_draft(draft_id, snoozed_until, path="data/drafts.json"):
    with draft_transaction(path):
        drafts = read_json(path)
        draft = drafts.get(draft_id)
        if not draft:
            return None
        draft["snoozed_until"] = snoozed_until
        write_json(path, drafts)
        return draft


def is_snoozed(draft):
    snoozed_until = draft.get("snoozed_until")
    if not snoozed_until:
        return False
    try:
        from datetime import datetime, timezone
        until_dt = datetime.fromisoformat(snoozed_until.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) < until_dt
    except Exception:
        return False
