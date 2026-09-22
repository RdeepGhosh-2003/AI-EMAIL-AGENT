"""In-process worker health, distinct from API reachability and key presence."""
import threading
import time

_owner = None
_state = {"phase": "not_running", "mailboxes": {}}
_lock = threading.Lock()


def update(phase, **values):
    global _owner
    with _lock:
        _owner = threading.current_thread()
        _state.update(phase=phase, updated_at=time.time(), **values)


def snapshot():
    with _lock:
        result = dict(_state)
        result['alive'] = bool(_owner and _owner.is_alive() and result['phase'] != 'stopped')
        if not result['alive']:
            result['phase'] = 'not_running'
        return result
