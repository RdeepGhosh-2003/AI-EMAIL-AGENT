"""Create a sanitized ZIP that is safe to give to another user."""

import ctypes
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "AI-Email-Agent-Share.zip"
ALLOWED_DIRECTORIES = {"api", "dashboard", "outlook", "scripts"}
ALLOWED_ROOT_FILES = {
    ".env.example", ".gitignore", "activity_log.py", "agent.py", "ai_engine.py",
    "check_agent_status.bat", "classifier.py", "config.yaml", "connect_email.py",
    "create_share_package.py",
    "Create_Sharing_Package.vbs", "Install_AI_Email_Agent.vbs", "delivery.py", "gemini_client.py",
    "install_autostart.bat", "install_startup_task.bat", "instance_lock.py", "launch_dashboard.py",
    "mailbox_errors.py", "openrouter_client.py", "Open_Dashboard.vbs", "README.md", "requirements.txt",
    "remove_startup_task.bat", "run_silent.vbs", "run.py", "security.py", "start.bat",
    "stop_agent.bat", "storage.py", "view_activity_logs.bat", "view_mail.py",
    "worker_state.py", "AI_Email_Agent_Setup_Guide.docx",
}
PRIVATE_NAMES = {"credentials.json", "token.pickle", "token_cache.json", "token_cache.tmp"}


def should_include(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if len(relative.parts) == 1:
        return relative.name in ALLOWED_ROOT_FILES
    return relative.parts[0] in ALLOWED_DIRECTORIES and not any(
        part == "__pycache__" or part in PRIVATE_NAMES or part.endswith((".pyc", ".pyo"))
        for part in relative.parts
    )


def create_package(output: Path = OUTPUT) -> Path:
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(ROOT.rglob("*")):
            if path.is_file() and should_include(path):
                archive.write(path, path.relative_to(ROOT.parent))
    return output


def main() -> int:
    output = create_package()
    message = f"Sharing package created:\n{output}\n\nPrivate tokens, credentials, email data, and API keys were excluded."
    if sys.platform == "win32":
        ctypes.windll.user32.MessageBoxW(0, message, "AI Email Agent", 0x40)
    else:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
