"""
api/server.py — Flask REST API for the web dashboard.
Exposes endpoints to list, edit, approve, and reject AI-generated drafts.

Run with: python api/server.py
"""

import json
import copy
import os
import mimetypes
import re
import subprocess
import threading
import uuid
from urllib.parse import urlparse
import sys
import yaml
from pathlib import Path
from datetime import datetime, timezone
from flask import Flask, jsonify, request, send_from_directory, redirect
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException
from dotenv import load_dotenv, set_key
from storage import read_json, write_json, draft_transaction, is_demo, get_retry_queue
from flask import g
from activity_log import log_activity, recent_activity

if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = ROOT / "dashboard"
app = Flask(__name__, static_folder=str(DASHBOARD_DIR), static_url_path="")
from api.inbox import inbox
app.register_blueprint(inbox)

DRAFTS_FILE = Path("data/drafts.json")
CONFIG_FILE = Path("config.yaml")
ENV_FILE = Path(".env")
ATTACHMENTS_DIR = Path("data/attachments")
MAX_ATTACHMENT_BYTES = 3 * 1024 * 1024
OUTLOOK_TOKEN_FILE = ROOT / "outlook" / "token_cache.json"
SETUP_GUIDE_FILE = ROOT / "AI_Email_Agent_Setup_Guide.docx"
_ACCOUNT_JOBS = {"outlook": {"state": "idle", "message": ""}}
_ACCOUNT_JOBS_LOCK = threading.Lock()
load_dotenv(ENV_FILE)


def api_key_status() -> dict:
    return {
        "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "gemini": bool(os.getenv("GEMINI_API_KEY")),
        "claude": bool(os.getenv("ANTHROPIC_API_KEY")),
    }


# ─── Helpers ───────────────────────────────────────────────────────────────

def load_drafts() -> dict:
    return read_json(DRAFTS_FILE)


def save_drafts(drafts: dict):
    write_json(DRAFTS_FILE, drafts)


from security import install_security
install_security(app, lambda: load_config())


@app.errorhandler(Exception)
def log_unhandled_error(error):
    if isinstance(error, HTTPException):
        return error
    log_activity("dashboard_error", path=request.path, error=error.__class__.__name__)
    app.logger.exception("Unhandled dashboard error")
    return jsonify(error="Unexpected dashboard error"), 500


@app.before_request
def serialize_draft_changes():
    if request.path.startswith('/api/drafts') and request.method != 'GET':
        g.draft_lock = draft_transaction(DRAFTS_FILE)
        g.draft_lock.__enter__()


@app.teardown_request
def release_draft_lock(error):
    lock = g.pop('draft_lock', None)
    if lock:
        lock.__exit__(None, None, None)


def attachment_payloads(draft: dict) -> list:
    payloads = []
    for item in draft.get("attachments", []):
        path = ATTACHMENTS_DIR / item["storage_name"]
        if not path.is_file():
            raise FileNotFoundError(f"Attachment is missing: {item['name']}")
        payloads.append({**item, "data": path.read_bytes()})
    return payloads


def remove_local_attachments(draft: dict):
    for item in draft.get("attachments", []):
        (ATTACHMENTS_DIR / item.get("storage_name", "__missing__")).unlink(missing_ok=True)


def load_config() -> dict:
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)


def get_outlook():
    from outlook.auth import get_outlook_token
    return get_outlook_token()


def account_connection_status() -> dict:
    with _ACCOUNT_JOBS_LOCK:
        jobs = copy.deepcopy(_ACCOUNT_JOBS)
    return {
        "outlook": {
            "credentials_ready": bool(os.getenv("AZURE_CLIENT_ID", "").strip()),
            "connected": OUTLOOK_TOKEN_FILE.is_file(),
            "tenant": os.getenv("AZURE_TENANT_ID", "").strip() or "common",
            **jobs["outlook"],
        },
    }


def _run_account_connection(provider: str):
    with _ACCOUNT_JOBS_LOCK:
        _ACCOUNT_JOBS[provider] = {"state": "connecting", "message": "Complete sign-in in the browser."}
    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        result = subprocess.run(
            [sys.executable, str(ROOT / "connect_email.py"), provider],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=360,
            creationflags=creation_flags,
        )
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout or "Authorization was not completed.").strip())
    except Exception as exc:
        app.logger.warning("%s connection failed: %s", provider, exc)
        log_activity("mailbox_connection_failed", provider=provider)
        with _ACCOUNT_JOBS_LOCK:
            _ACCOUNT_JOBS[provider] = {"state": "error", "message": "Sign-in was not completed. Check the setup steps and try again."}
    else:
        log_activity("mailbox_connection_completed", provider=provider)
        with _ACCOUNT_JOBS_LOCK:
            _ACCOUNT_JOBS[provider] = {"state": "connected", "message": "Account connected."}


# ─── Serve Dashboard ───────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(DASHBOARD_DIR, "index.html")


@app.route("/login")
def login():
    return send_from_directory(DASHBOARD_DIR, "login.html")


@app.get("/setup-guide")
def setup_guide():
    if not SETUP_GUIDE_FILE.is_file():
        return jsonify(error="Setup guide is not installed"), 404
    return send_from_directory(ROOT, SETUP_GUIDE_FILE.name, as_attachment=True)


@app.route("/<path:filename>")
def serve_static(filename):
    if filename == "login.html":
        return redirect("/login")
    if (DASHBOARD_DIR / filename).exists():
        return send_from_directory(DASHBOARD_DIR, filename)
    return jsonify({"error": "File not found"}), 404



# ─── API Endpoints ─────────────────────────────────────────────────────────

def save_config(config: dict):
    temporary = CONFIG_FILE.with_name(CONFIG_FILE.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(yaml.safe_dump(config, sort_keys=False), encoding='utf-8')
    temporary.replace(CONFIG_FILE)


def safe_draft_details(draft: dict) -> dict:
    return {
        "draft_id": draft.get("id"),
        "platform": draft.get("platform"),
        "subject": draft.get("subject", "")[:120],
        "sender": draft.get("sender", "")[:160],
        "status": draft.get("status"),
    }


def load_full_original(draft):
    if draft.get('original_body_complete') or len(draft.get('original_body', '')) < 1000 or is_demo(draft):
        return
    if draft['platform'] == 'outlook':
        import requests
        from urllib.parse import quote
        from outlook.fetcher import _parse_message
        response = requests.get('https://graph.microsoft.com/v1.0/me/messages/' + quote(draft['email_id'], safe=''),
            headers={'Authorization':'Bearer ' + get_outlook(), 'Prefer':'outlook.body-content-type="text"'}, timeout=20)
        response.raise_for_status()
        message = _parse_message(response.json())
    else:
        raise ValueError('This installation supports Outlook drafts only')
    draft['original_body'] = message.get('body', '')
    draft['original_body_complete'] = True
    draft['message_id'] = message.get('message_id')


@app.post('/api/drafts/<draft_id>/original')
def refresh_original(draft_id):
    drafts = load_drafts()
    draft = drafts.get(draft_id)
    if not draft:
        return jsonify(error='Draft not found'), 404
    try:
        load_full_original(draft)
        save_drafts(drafts)
        return jsonify(draft=draft)
    except Exception as error:
        from mailbox_errors import describe
        message, status = describe(error, draft.get('platform', 'mailbox'))
        return jsonify(error=message), status


@app.route("/api/status")
def status():
    """Agent and draft statistics."""
    drafts = load_drafts()
    config = load_config()
    ai_model = config.get("ai", {}).get("model", "openai")
    ai_configured = api_key_status().get(ai_model, False)
    counts = {"pending": 0, "approved": 0, "rejected": 0, "deleted": 0}
    real_drafts = [d for d in drafts.values() if not is_demo(d)]
    for d in real_drafts:
        s = d.get("status", "pending")
        counts[s] = counts.get(s, 0) + 1

    return jsonify({
        "status": "available",
        "worker": __import__('worker_state').snapshot(),
        "ai_model": ai_model,
        "ai_configured": ai_configured,
        "ai_providers_configured": api_key_status(),
        "retry_queue": get_retry_queue(),
        "total": len(real_drafts),
        "demo_hidden": len(drafts) - len(real_drafts),
        "pending": counts["pending"],
        "approved": counts["approved"],
        "rejected": counts["rejected"],
        "deleted": counts["deleted"],
        "timestamp": datetime.now().isoformat(),
    })


@app.route("/api/stop", methods=["POST"])
def stop_agent():
    """Stops the AI Email Agent and shuts down the server process."""
    def shutdown():
        import time
        import os
        time.sleep(0.5)
        os._exit(0)

    import threading
    threading.Thread(target=shutdown, daemon=True).start()
    log_activity("app_stop_requested", remote_addr=request.remote_addr)
    return jsonify({"success": True, "message": "Agent stopping..."})


@app.route("/api/config", methods=["GET", "PUT"])
def manage_config():
    """Get or update project config.yaml."""
    if request.method == "GET":
        config = load_config()
        config.get('agent', {}).pop('pin_code', None)
        config.get('agent', {}).pop('pin_hash', None)
        config['api_keys_configured'] = api_key_status()
        return jsonify(config)

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict) or any(not isinstance(data.get(key, {}), dict) for key in ('ai', 'agent', 'user_style', 'platforms', 'api_keys')):
        return jsonify(message="Settings must be an object"), 400
    try:
        if 'check_interval_seconds' in data.get('agent', {}):
            interval = int(data['agent']['check_interval_seconds'])
            if not 30 <= interval <= 3600:
                raise ValueError()
        if 'confidence_threshold' in data.get('agent', {}):
            threshold = float(data['agent']['confidence_threshold'])
            if not .85 <= threshold <= 1:
                raise ValueError()
    except (TypeError, ValueError):
        return jsonify(message="Polling must be 30–3600 seconds and confidence 0.85–1.0"), 400
    if data.get('ai', {}).get('model', 'openai') not in ('openrouter', 'openai', 'gemini', 'claude'):
        return jsonify(message="Unknown AI provider"), 400
    config = load_config()

    if "ai" in data:
        config.setdefault("ai", {})["model"] = data["ai"].get("model", config["ai"].get("model", "openai"))
        if "openrouter_model" in data["ai"]:
            model = str(data["ai"]["openrouter_model"]).strip()
            if not model or "/" not in model or not all(char.isalnum() or char in ".-_:~/" for char in model):
                return jsonify(message="Enter a valid OpenRouter model slug such as google/gemini-2.5-flash"), 400
            config["ai"]["openrouter_model"] = model

    if "user_style" in data:
        config.setdefault("user_style", {})["tone"] = data["user_style"].get("tone", config["user_style"].get("tone", "professional"))
        config.setdefault("user_style", {})["name"] = data["user_style"].get("name", config["user_style"].get("name", "Bhagyaraj"))
        if "instructions" in data["user_style"]:
            config["user_style"]["instructions"] = data["user_style"]["instructions"]

    if "agent" in data:
        config.setdefault("agent", {})["check_interval_seconds"] = int(data["agent"].get("check_interval_seconds", config["agent"].get("check_interval_seconds", 120)))
        if "confidence_threshold" in data["agent"]:
            config["agent"]["confidence_threshold"] = float(data["agent"]["confidence_threshold"])
        if "auto_approve" in data["agent"]:
            config["agent"]["auto_approve"] = bool(data["agent"]["auto_approve"])
        if "sound_fx" in data["agent"]:
            config["agent"]["sound_fx"] = bool(data["agent"]["sound_fx"])
        if "pin_security" in data["agent"]:
            config["agent"]["pin_security"] = bool(data["agent"]["pin_security"])
        if data["agent"].get("pin_code"):
            pin_code = str(data["agent"]["pin_code"])
            if not pin_code.isdigit() or not 4 <= len(pin_code) <= 12:
                return jsonify(message="PIN must contain 4 to 12 digits"), 400
            from werkzeug.security import generate_password_hash
            pin_hash = generate_password_hash(pin_code)
            ENV_FILE.touch(exist_ok=True)
            set_key(str(ENV_FILE), "DASHBOARD_PIN_HASH", pin_hash)
            os.environ["DASHBOARD_PIN_HASH"] = pin_hash
            set_key(str(ENV_FILE), "DASHBOARD_PIN_SECURITY", "true")
            os.environ["DASHBOARD_PIN_SECURITY"] = "true"
            config["agent"]["pin_security"] = True
            config["agent"].pop("pin_hash", None)
            config["agent"].pop("pin_code", None)
        if "theme" in data["agent"]:
            config["agent"]["theme"] = str(data["agent"]["theme"])
        if "vip_contacts" in data["agent"]:
            contacts = data["agent"]["vip_contacts"]
            if isinstance(contacts, str):
                contacts = [item.strip() for item in contacts.split(",") if item.strip()]
            if not isinstance(contacts, list) or not all(isinstance(item, str) for item in contacts):
                return jsonify(message="VIP contacts must be a comma-separated list"), 400
            config["agent"]["vip_contacts"] = [item.strip() for item in contacts if item.strip()]

    if "platforms" in data:
        config["platforms"] = {"outlook": bool(data["platforms"].get("outlook", True))}

    if config.get('agent', {}).get('pin_security') and not (
        os.getenv("DASHBOARD_PIN_HASH")
        or os.getenv("DASHBOARD_PIN")
        or config['agent'].get('pin_code')
        or config['agent'].get('pin_hash')
    ):
        return jsonify(message="Set a PIN before enabling PIN security"), 400
    key_names = {"openrouter": "OPENROUTER_API_KEY", "openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY", "claude": "ANTHROPIC_API_KEY"}
    # Validate all keys before persisting any of them.
    if any(provider in key_names and str(value).strip() and len(str(value).strip()) < 12
           for provider, value in (data.get('api_keys') or {}).items()):
        return jsonify(message="An API key looks too short"), 400
    for provider, value in (data.get("api_keys") or {}).items():
        if provider not in key_names or not str(value).strip():
            continue
        key = str(value).strip()
        if len(key) < 12:
            return jsonify(message=f"The {provider} API key looks too short"), 400
        ENV_FILE.touch(exist_ok=True)
        set_key(str(ENV_FILE), key_names[provider], key)
        os.environ[key_names[provider]] = key

    save_config(config)
    log_activity("settings_changed", remote_addr=request.remote_addr, sections=[key for key in data.keys() if key != "api_keys"])
    public_config = copy.deepcopy(config)
    public_config.get('agent', {}).pop('pin_code', None)
    public_config.get('agent', {}).pop('pin_hash', None)
    public_config['api_keys_configured'] = api_key_status()
    return jsonify({"success": True, "config": public_config, "message": "Settings saved successfully! ⚙️"})


@app.get("/api/activity")
def activity():
    try:
        limit = int(request.args.get("limit", 100))
    except ValueError:
        limit = 100
    return jsonify(events=recent_activity(limit))


@app.get("/api/accounts/status")
def account_status():
    return jsonify(account_connection_status())


@app.post("/api/accounts/outlook/config")
def save_outlook_config():
    data = request.get_json(silent=True) or {}
    client_id = str(data.get("client_id", "")).strip()
    tenant_id = str(data.get("tenant_id", "")).strip() or "common"
    identifier = re.compile(r"^[A-Za-z0-9._-]{8,128}$")
    if not identifier.fullmatch(client_id):
        return jsonify(error="Enter a valid Microsoft Application client ID."), 400
    if tenant_id != "common" and not identifier.fullmatch(tenant_id):
        return jsonify(error="Enter a valid tenant ID or use common."), 400
    ENV_FILE.touch(exist_ok=True)
    set_key(str(ENV_FILE), "AZURE_CLIENT_ID", client_id)
    set_key(str(ENV_FILE), "AZURE_TENANT_ID", tenant_id)
    os.environ["AZURE_CLIENT_ID"] = client_id
    os.environ["AZURE_TENANT_ID"] = tenant_id
    log_activity("outlook_config_saved", remote_addr=request.remote_addr, tenant=tenant_id)
    return jsonify(success=True, message="Microsoft app details saved. Now click Connect Microsoft.")


@app.post("/api/accounts/<provider>/connect")
def connect_account(provider):
    if provider != "outlook":
        return jsonify(error="Unknown email provider."), 404
    status = account_connection_status()[provider]
    if not status["credentials_ready"]:
        return jsonify(error="Please save the Microsoft client ID first."), 400
    with _ACCOUNT_JOBS_LOCK:
        if _ACCOUNT_JOBS[provider]["state"] == "connecting":
            return jsonify(error="A sign-in is already in progress."), 409
        _ACCOUNT_JOBS[provider] = {"state": "connecting", "message": "Opening browser sign-in…"}
    threading.Thread(target=_run_account_connection, args=(provider,), daemon=True).start()
    log_activity("mailbox_connection_started", provider=provider, remote_addr=request.remote_addr)
    return jsonify(success=True, message="Sign-in opened in your browser. Complete the provider confirmation there."), 202


@app.route('/api/drafts/<draft_id>/rewrite', methods=['POST'])
def rewrite_draft(draft_id):
    """Return an unsaved alternative for review; never send or alter a draft."""
    draft = load_drafts().get(draft_id)
    if not draft:
        return jsonify(error='Draft not found'), 404
    if draft.get('status') != 'pending':
        return jsonify(error='Only pending drafts can be rewritten'), 400
    try:
        load_full_original(draft)
    except Exception:
        return jsonify(error='Could not load the complete original email. Reconnect the mailbox before rewriting this older draft.'), 502
    data = request.get_json(silent=True) or {}
    action = data.get('action')
    if action not in ('regenerate', 'shorten', 'tone'):
        return jsonify(error='Unknown writing action'), 400
    config = copy.deepcopy(load_config())
    from ai_engine import generate_reply
    from ai_engine import available_ai_providers
    if not available_ai_providers(config):
        return jsonify(error='Connect an AI provider API key to use writing tools. You can still edit this draft manually.'), 503
    tone = data.get('tone', 'professional')
    if tone not in ('professional', 'casual', 'formal'):
        return jsonify(error='Unknown tone'), 400
    if action == 'tone':
        config.setdefault('user_style', {})['tone'] = tone
    instruction = {'regenerate': 'Write a fresh alternative reply.', 'shorten': 'Shorten the current reply while preserving all facts and commitments.', 'tone': f'Rewrite the current reply with a {tone} tone, preserving all facts and commitments.'}[action]
    email = dict(sender=draft.get('sender'), subject=draft.get('subject'), body=draft.get('original_body', ''))
    config['_rewrite_instruction'] = instruction
    config['_current_reply'] = str(data.get('reply', draft.get('ai_reply', '')))[:20000]
    try:
        return jsonify(ai_reply=generate_reply(email, config=config))
    except Exception:
        app.logger.exception('Reply rewrite failed')
        return jsonify(error='The AI provider could not complete this rewrite. Please try again.'), 502



@app.route("/api/drafts")
def get_drafts():
    """Returns all drafts, sorted newest first."""
    drafts = load_drafts()
    draft_list = sorted(
        (dict(draft, is_demo=is_demo(draft), original_body_complete=draft.get('original_body_complete', len(draft.get('original_body', '')) < 1000))
         for draft in drafts.values() if request.args.get('include_demo') == 'true' or not is_demo(draft)),
        key=lambda x: x.get("created_at", ""),
        reverse=True,
    )
    return jsonify(draft_list)


@app.route("/api/inbox/outlook/draft-reply", methods=["POST"])
def create_outlook_draft_from_inbox():
    data = request.get_json(silent=True) or {}
    message_id = str(data.get("message_id", "")).strip()
    if not message_id:
        return jsonify(error="Choose an email first"), 400
    drafts = load_drafts()
    for draft in drafts.values():
        if draft.get("email_id") == message_id and draft.get("status") == "pending":
            return jsonify(draft=draft, existing=True, message="This email already has a pending draft.")
    try:
        from urllib.parse import quote
        import requests
        from outlook.fetcher import _parse_message, fetch_thread_history
        from outlook.draft import create_draft
        from classifier import classify_email
        from ai_engine import generate_reply
        from agent import add_draft

        token = get_outlook()
        headers = {"Authorization": "Bearer " + token, "Prefer": 'outlook.body-content-type="text"'}
        response = requests.get(
            "https://graph.microsoft.com/v1.0/me/messages/" + quote(message_id, safe=""),
            headers=headers,
            timeout=20,
        )
        response.raise_for_status()
        email = _parse_message(response.json())
        config = load_config()
        classification = classify_email(email, config)
        thread_history = []
        if email.get("thread_id"):
            thread_history = fetch_thread_history(token, email["thread_id"], exclude_id=message_id)
        reply_body = generate_reply(email, thread_history, config)
        platform_draft_id = None
        try:
            platform_draft_id = create_draft(token, email, reply_body)
        except Exception:
            app.logger.exception("Could not create Outlook provider draft from inbox")
        draft_id = add_draft(drafts, email, reply_body, platform_draft_id, classification)
        draft = drafts[draft_id]
        log_activity(
            "draft_saved",
            draft_id=draft_id,
            platform="outlook",
            subject=email.get("subject", "")[:120],
            sender=email.get("sender", "")[:160],
            provider_draft_created=bool(platform_draft_id),
        )
        return jsonify(draft=draft, existing=False, provider_draft_created=bool(platform_draft_id))
    except Exception as error:
        from mailbox_errors import describe
        message, status = describe(error, "outlook")
        return jsonify(error=message), status


@app.route("/api/drafts/<draft_id>/snooze", methods=["PUT", "DELETE"])
def snooze_draft_route(draft_id):
    drafts = load_drafts()
    draft = drafts.get(draft_id)
    if not draft:
        return jsonify(error="Draft not found"), 404
    if draft.get("status") != "pending":
        return jsonify(error="Only pending drafts can be snoozed"), 400
    if request.method == "DELETE":
        draft.pop("snoozed_until", None)
        save_drafts(drafts)
        log_activity("draft_snooze_cleared", **safe_draft_details(draft))
        return jsonify(draft=draft)
    data = request.get_json(silent=True) or {}
    snoozed_until = str(data.get("snoozed_until", "")).strip()
    try:
        parsed = datetime.fromisoformat(snoozed_until.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return jsonify(error="Choose a valid snooze time"), 400
    if parsed <= datetime.now(timezone.utc):
        return jsonify(error="Choose a future snooze time"), 400
    draft["snoozed_until"] = snoozed_until
    save_drafts(drafts)
    log_activity("draft_snoozed", **safe_draft_details(draft), snoozed_until=snoozed_until)
    return jsonify(draft=draft)


@app.route("/api/drafts/bulk-delete", methods=["POST"])
def bulk_delete_drafts():
    drafts = load_drafts()
    ids = list(dict.fromkeys((request.get_json(silent=True) or {}).get("ids", [])))
    if not ids:
        return jsonify(error="Select at least one draft"), 400
    selected = [drafts[item] for item in ids if item in drafts]
    if len(selected) != len(ids):
        return jsonify(error="One or more drafts no longer exist"), 404
    if any(draft.get("status") in ("approved", "deleted") for draft in selected):
        return jsonify(error="Sent or already deleted drafts cannot be deleted"), 400
    deleted_at = datetime.now().isoformat()
    provider_cleanup_failures = []
    for draft in selected:
        platform_draft_id = draft.get("platform_draft_id")
        if platform_draft_id:
            try:
                if draft.get("platform") == "outlook":
                    from outlook.draft import delete_draft
                    delete_draft(get_outlook(), platform_draft_id)
                else:
                    raise ValueError("This installation supports Outlook drafts only")
            except Exception as exc:
                # Moving a draft to Deleted is a local action. A temporary provider
                # outage should not leave the dashboard unusable or expose a raw
                # OAuth/HTTP exception to the user.
                app.logger.warning(
                    "Could not remove platform draft %s for local draft %s: %s",
                    platform_draft_id,
                    draft.get("id", "unknown"),
                    exc,
                )
                draft["provider_cleanup_pending"] = True
                provider_cleanup_failures.append(draft.get("subject") or "Untitled draft")
            else:
                draft.pop("provider_cleanup_pending", None)
        # Keep attachments so Undo restores the full reviewed draft.
        draft["status"] = "deleted"
        draft["deleted_at"] = deleted_at
    save_drafts(drafts)
    response = {"deleted": len(selected), "deleted_at": deleted_at}
    if provider_cleanup_failures:
        response["warning"] = (
            f"Moved to Deleted, but {len(provider_cleanup_failures)} draft"
            f"{'s were' if len(provider_cleanup_failures) != 1 else ' was'} not removed "
            "from the email provider. Check your connection and remove there manually."
        )
        response["provider_cleanup_failed"] = len(provider_cleanup_failures)
    return jsonify(response)


@app.route("/api/drafts/<draft_id>/attachments", methods=["POST"])
def add_attachments(draft_id):
    drafts = load_drafts()
    draft = drafts.get(draft_id)
    if not draft:
        return jsonify(error="Draft not found"), 404
    if draft.get("status") != "pending":
        return jsonify(error="Attachments can only be added to pending drafts"), 400
    files = [file for file in request.files.getlist("files") if file.filename]
    if not files:
        return jsonify(error="Choose at least one file"), 400
    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
    added = []
    try:
        for upload in files:
            upload.stream.seek(0, 2)
            size = upload.stream.tell()
            upload.stream.seek(0)
            if size > MAX_ATTACHMENT_BYTES:
                raise ValueError(f"{upload.filename} is larger than 3 MB")
            safe_name = secure_filename(upload.filename) or "attachment"
            attachment_id = uuid.uuid4().hex
            storage_name = f"{attachment_id}_{safe_name}"
            upload.save(ATTACHMENTS_DIR / storage_name)
            added.append({
                "id": attachment_id,
                "name": safe_name,
                "size": size,
                "content_type": upload.mimetype or mimetypes.guess_type(safe_name)[0] or "application/octet-stream",
                "storage_name": storage_name,
            })
    except Exception as exc:
        for item in added:
            (ATTACHMENTS_DIR / item["storage_name"]).unlink(missing_ok=True)
        return jsonify(error=str(exc)), 400
    draft.setdefault("attachments", []).extend(added)
    save_drafts(drafts)
    log_activity("draft_attachment_added", **safe_draft_details(draft), attachment_count=len(added))
    return jsonify(added=len(added), attachments=draft["attachments"])


@app.route("/api/drafts/<draft_id>/attachments/<attachment_id>", methods=["DELETE"])
def remove_attachment(draft_id, attachment_id):
    drafts = load_drafts()
    draft = drafts.get(draft_id)
    if not draft:
        return jsonify(error="Draft not found"), 404
    if draft.get("status") != "pending":
        return jsonify(error="Attachments can only be removed from pending drafts"), 400
    attachments = draft.get("attachments", [])
    item = next((entry for entry in attachments if entry.get("id") == attachment_id), None)
    if not item:
        return jsonify(error="Attachment not found"), 404
    if item.get('provider_attachment_id') and draft.get('platform') == 'outlook':
        try:
            from outlook.draft import remove_attachment as remove_remote
            remove_remote(get_outlook(), draft['platform_draft_id'], item['provider_attachment_id'])
        except Exception:
            return jsonify(error="Could not remove the provider attachment. Please retry."), 502
    (ATTACHMENTS_DIR / item["storage_name"]).unlink(missing_ok=True)
    draft["attachments"] = [entry for entry in attachments if entry.get("id") != attachment_id]
    save_drafts(drafts)
    log_activity("draft_attachment_removed", **safe_draft_details(draft))
    return jsonify(attachments=draft["attachments"])


@app.route("/api/drafts/<draft_id>/links", methods=["POST"])
def add_link(draft_id):
    drafts = load_drafts()
    draft = drafts.get(draft_id)
    if not draft:
        return jsonify(error="Draft not found"), 404
    if draft.get("status") != "pending":
        return jsonify(error="Links can only be added to pending drafts"), 400
    data = request.get_json(silent=True) or {}
    url = str(data.get("url", "")).strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return jsonify(error="Enter a valid http or https link"), 400
    kind = data.get("kind", "link")
    if kind not in ("link", "drive"):
        return jsonify(error="Unknown link type"), 400
    if kind == "drive" and not (parsed.netloc == "drive.google.com" or parsed.netloc.endswith(".drive.google.com")):
        return jsonify(error="Enter a Google Drive share link"), 400
    label = str(data.get("label", "")).strip()[:120] or ("Google Drive file" if kind == "drive" else parsed.netloc)
    draft.setdefault("links", []).append({"id": uuid.uuid4().hex, "url": url, "label": label, "kind": kind})
    save_drafts(drafts)
    log_activity("draft_link_added", **safe_draft_details(draft), kind=kind)
    return jsonify(links=draft["links"])


@app.route("/api/drafts/<draft_id>/links/<link_id>", methods=["DELETE"])
def remove_link(draft_id, link_id):
    drafts = load_drafts()
    draft = drafts.get(draft_id)
    if not draft:
        return jsonify(error="Draft not found"), 404
    if draft.get("status") != "pending":
        return jsonify(error="Links can only be removed from pending drafts"), 400
    links = draft.get("links", [])
    if not any(item.get("id") == link_id for item in links):
        return jsonify(error="Link not found"), 404
    draft["links"] = [item for item in links if item.get("id") != link_id]
    save_drafts(drafts)
    log_activity("draft_link_removed", **safe_draft_details(draft))
    return jsonify(links=draft["links"])


@app.route("/api/drafts/<draft_id>/restore", methods=["POST"])
def restore_draft(draft_id):
    drafts = load_drafts()
    draft = drafts.get(draft_id)
    if not draft:
        return jsonify(error="Draft not found"), 404
    previous_status = draft.get("status")
    if previous_status not in ("rejected", "deleted"):
        return jsonify(error="Only discarded or deleted drafts can be restored"), 400

    # When provider cleanup failed, the remote draft still exists and can be
    # reused. Otherwise recreate a provider draft before returning it to Pending.
    if draft.get("platform_draft_id") and not draft.get("provider_cleanup_pending") and not is_demo(draft):
        email_stub = {"id": draft["email_id"], "thread_id": draft.get("thread_id"), "sender": draft["sender"], "subject": draft["subject"]}
        try:
            if draft["platform"] == "outlook":
                from outlook.draft import create_draft
                draft["platform_draft_id"] = create_draft(get_outlook(), email_stub, draft["ai_reply"])
            else:
                raise ValueError("This installation supports Outlook drafts only")
        except Exception as exc:
            return jsonify(error=f"Could not recreate the provider draft: {exc}"), 502
        for item in draft.get('attachments', []):
            item.pop('provider_attachment_id', None)
    draft["status"] = "pending"
    draft.pop("rejected_at", None)
    draft.pop("deleted_at", None)
    draft.pop("provider_cleanup_pending", None)
    save_drafts(drafts)
    log_activity("draft_restored", **safe_draft_details(draft), restored_from=previous_status)
    return jsonify(draft=draft, restored_from=previous_status)


@app.route("/api/drafts/<draft_id>/approve", methods=["POST"])
def approve_draft(draft_id):
    drafts = load_drafts()
    draft = drafts.get(draft_id)
    if not draft:
        return jsonify(error="Draft not found"), 404
    if draft.get("status") != "pending":
        return jsonify(error="Only pending drafts can be sent"), 400
    if is_demo(draft):
        return jsonify(error="Demo drafts cannot be sent"), 400
    if not draft.get("platform_draft_id"):
        return jsonify(error="No provider draft exists. Edit and save the reply to create one before sending."), 409
    from delivery import sync_reply, send_reply
    try:
        sync_reply(draft, get_outlook, attachment_payloads(draft), lambda: save_drafts(drafts))
    except Exception:
        app.logger.exception("Reply synchronization failed")
        return jsonify(error="Could not sync the reply and attachments. Nothing was sent; check your connection and retry."), 502
    try:
        send_reply(draft, get_outlook)
    except Exception:
        app.logger.exception("Provider did not confirm delivery")
        return jsonify(error="Sending was not confirmed. Check your provider's Sent folder before retrying. The draft remains pending."), 502
    draft["status"] = "approved"
    draft["approved_at"] = datetime.now().isoformat()
    # Keep attachment metadata and reviewed text as the sent record.
    save_drafts(drafts)
    log_activity("draft_approved_sent", **safe_draft_details(draft))
    return jsonify(success=True, message="Email provider accepted the reply for sending.", draft=draft)


@app.route("/api/drafts/<draft_id>/reject", methods=["DELETE"])
def reject_draft(draft_id):
    drafts = load_drafts()
    draft = drafts.get(draft_id)
    if not draft:
        return jsonify(error="Draft not found"), 404
    if draft.get("status") != "pending":
        return jsonify(error="Only pending drafts can be discarded"), 400
    warning = None
    if draft.get("platform_draft_id") and not is_demo(draft):
        try:
            if draft["platform"] == "outlook":
                from outlook.draft import delete_draft
                delete_draft(get_outlook(), draft["platform_draft_id"])
            else:
                raise ValueError("Unsupported email provider")
            draft.pop("provider_cleanup_pending", None)
        except Exception:
            app.logger.exception("Provider cleanup failed")
            draft["provider_cleanup_pending"] = True
            warning = "Discarded locally, but the provider draft could not be removed. Check your connection."
    draft["status"] = "rejected"
    draft["rejected_at"] = datetime.now().isoformat()
    save_drafts(drafts)
    log_activity("draft_rejected", **safe_draft_details(draft), provider_cleanup_pending=draft.get("provider_cleanup_pending", False))
    return jsonify(success=True, message="Draft discarded", draft=draft, warning=warning)


@app.route("/api/drafts/<draft_id>/edit", methods=["PUT"])
def edit_draft(draft_id):
    drafts = load_drafts()
    draft = drafts.get(draft_id)
    if not draft:
        return jsonify(error="Draft not found"), 404
    if draft.get("status") != "pending":
        return jsonify(error="Only pending drafts can be edited"), 400
    new_reply = (request.get_json(silent=True) or {}).get("ai_reply", "")
    if not isinstance(new_reply, str) or not new_reply.strip():
        return jsonify(error="Reply body cannot be empty"), 400
    candidate = copy.deepcopy(draft)
    candidate["ai_reply"] = new_reply.strip()
    candidate["edited"] = True
    candidate["edited_at"] = datetime.now().isoformat()
    if not is_demo(candidate):
        from delivery import sync_reply
        try:
            # Outlook uploads are deferred until send so a partial edit failure
            # cannot orphan uploaded attachment IDs or duplicate them on retry.
            sync_reply(candidate, get_outlook, [])
        except Exception:
            app.logger.exception("Edit synchronization failed")
            return jsonify(error="Could not sync the edit. Your text is still in the editor; check the connection and retry."), 502
    drafts[draft_id] = candidate
    save_drafts(drafts)

    # Record style difference for continuous AI learning
    original_ai = draft.get("ai_reply", "")
    if original_ai and original_ai != candidate["ai_reply"]:
        try:
            from ai_engine import record_style_diff
            record_style_diff(original_ai, candidate["ai_reply"], context=candidate.get("subject", ""))
        except Exception:
            pass

    log_activity("draft_edited", **safe_draft_details(candidate))
    return jsonify(success=True, draft=candidate, message="Demo edit saved locally." if is_demo(candidate) else "Reply saved and synchronized.")


# ─── Entry Point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    from instance_lock import acquire_dashboard_lock

    config = load_config()
    host = config.get("dashboard", {}).get("host", "127.0.0.1")
    port = config.get("dashboard", {}).get("port", 5001)
    dashboard_lock = acquire_dashboard_lock()
    if dashboard_lock is None:
        print(f"Dashboard is already running at http://localhost:{port}")
        raise SystemExit(0)
    print(f"\n  🌐 Dashboard → http://localhost:{port}")
    print(f"  📡 API       → http://localhost:{port}/api/drafts\n")
    app.run(host=host, debug=False, port=port, use_reloader=False)
