"""Cross-process lock that prevents duplicate dashboard servers."""
from pathlib import Path


def acquire_dashboard_lock():
    """Return an open lock handle, or ``None`` when another instance owns it."""
    lock_path = Path(__file__).resolve().parent / "data" / ".dashboard.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch(exist_ok=True)
    handle = open(lock_path, "r+b")
    if lock_path.stat().st_size == 0:
        handle.write(b"1")
        handle.flush()
    handle.seek(0)

    try:
        if __import__("os").name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, BlockingIOError):
        handle.close()
        return None
    return handle
