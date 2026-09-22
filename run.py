"""
run.py — Starts both the AI agent and the dashboard API server
as parallel background threads.

Usage:
    python run.py
"""

import threading
import sys
from pathlib import Path

# Force UTF-8 console output encoding on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def run_server():
    """Starts the Flask dashboard API server."""
    import yaml
    with open("config.yaml") as f:
        config = yaml.safe_load(f)
    host = config.get("dashboard", {}).get("host", "127.0.0.1")
    port = config.get("dashboard", {}).get("port", 5001)

    # Suppress Flask startup banner
    import logging
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)

    sys.path.insert(0, str(Path(__file__).parent))
    from api.server import app
    app.run(host=host, debug=False, port=port, use_reloader=False, threaded=True)


def run_agent():
    """Starts the AI email agent loop."""
    from agent import run_agent as _run
    _run()


if __name__ == "__main__":
    from instance_lock import acquire_dashboard_lock

    dashboard_lock = acquire_dashboard_lock()

    import yaml
    with open("config.yaml") as f:
        config = yaml.safe_load(f)
    port = config.get("dashboard", {}).get("port", 5001)

    if dashboard_lock is None:
        print(f"AI Email Agent is already running at http://localhost:{port}")
        sys.exit(0)

    print()
    print("  ╔══════════════════════════════════════════╗")
    print("  ║     🤖  AI Email Agent — Launcher        ║")
    print("  ╚══════════════════════════════════════════╝")
    print()

    # Start dashboard server in background thread
    server_thread = threading.Thread(target=run_server, daemon=True, name="DashboardServer")
    server_thread.start()
    
    print(f"  🌐 Dashboard started → http://localhost:{port}")
    print("  Open the dashboard from Open_Dashboard when needed.")
    print()

    # Run agent in main thread (blocking)
    try:
        run_agent()
    except KeyboardInterrupt:
        print("\n\n  👋 Agent stopped. Goodbye!")
        sys.exit(0)
