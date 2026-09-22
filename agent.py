"""
agent.py — Main AI Email Reply Agent orchestrator.
Run this to start the agent loop.

Usage:
    python agent.py
"""

import time
import json
import uuid
import yaml
import sys
import os
import io
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from storage import read_json, write_json, draft_transaction
import worker_state
from activity_log import log_activity

# Force UTF-8 console output encoding on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

load_dotenv()


# ─── Config ────────────────────────────────────────────────────────────────

def load_config() -> dict:
    with open("config.yaml") as f:
        return yaml.safe_load(f)


def save_config(config: dict):
    public_config = {key: value for key, value in config.items() if not str(key).startswith("_")}
    temporary = Path("config.yaml." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(yaml.safe_dump(public_config, sort_keys=False), encoding="utf-8")
    temporary.replace("config.yaml")


def persist_provider_switch_if_needed(config: dict, email: dict, step: str):
    provider = config.get("_ai_provider_used")
    preferred = (config.get("ai", {}).get("model") or "openai").lower()
    if not provider or provider == preferred or config.get("_ai_provider_error_type") != "quota":
        return
    updated = load_config()
    updated.setdefault("ai", {})["model"] = provider
    save_config(updated)
    log_activity(
        "ai_provider_switched",
        step=step,
        from_provider=preferred,
        to_provider=provider,
        reason="quota",
        email_id=email.get("id", ""),
        subject=email.get("subject", "")[:120],
    )


# ─── Draft Store (JSON file used as local database) ───────────────────────

DRAFTS_FILE = Path("data/drafts.json")
PROCESSED_FILE = Path("data/processed_ids.json")


def load_drafts() -> dict:
    return read_json(DRAFTS_FILE)


def save_drafts(drafts: dict):
    write_json(DRAFTS_FILE, drafts)


def load_processed() -> set:
    if PROCESSED_FILE.exists():
        with open(PROCESSED_FILE) as f:
            return set(json.load(f))
    return set()


def save_processed(ids: set):
    PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROCESSED_FILE, "w") as f:
        json.dump(list(ids), f)


def add_draft(
    drafts: dict,
    email: dict,
    reply_body: str,
    platform_draft_id: str,
    classification: dict,
) -> str:
    """Adds a processed draft to the local store and returns its UUID."""
    draft_id = str(uuid.uuid4())

    # Thread conflict detection
    thread_id = email.get("thread_id", "")
    has_conflict = False
    for existing_id, existing in drafts.items():
        if existing.get("status") == "pending" and existing_id != draft_id:
            if thread_id and existing.get("thread_id") == thread_id:
                has_conflict = True
                break
            if existing.get("subject") == email.get("subject") and existing.get("sender") == email.get("sender"):
                has_conflict = True
                break

    entry = {
        "id": draft_id,
        "platform": email.get("platform", "unknown"),
        "platform_draft_id": platform_draft_id,
        "email_id": email["id"],
        "thread_id": email.get("thread_id", ""),
        "subject": email.get("subject", ""),
        "sender": email.get("sender", ""),
        "sender_name": email.get("sender_name", ""),
        "original_body": email.get("body", ""),
        "original_body_complete": True,
        "message_id": email.get("message_id"),
        "is_demo": str(email["id"]).startswith("mock_"),
        "is_vip": classification.get("is_vip", False),
        "thread_conflict": has_conflict,
        "ai_provider": classification.get("ai_provider"),
        "ai_reply": reply_body,
        "classification": classification,
        "status": "pending",  # pending | approved | rejected
        "edited": False,
        "created_at": datetime.now().isoformat(),
    }
    with draft_transaction(DRAFTS_FILE):
        latest = load_drafts()
        latest[draft_id] = entry
        save_drafts(latest)
        drafts.clear()
        drafts.update(latest)
    return draft_id


# ─── Core Email Processing Pipeline ───────────────────────────────────────

def should_skip_sender(email: dict, config: dict) -> bool:
    sender = email.get("sender", "").lower()
    patterns = config.get("filters", {}).get("skip_senders_containing", [])
    return any(p.lower() in sender for p in patterns)


def process_email(
    email: dict,
    platform: str,
    service_or_token,
    config: dict,
    drafts: dict,
    processed_ids: set,
) -> bool:
    """
    Runs a single email through the full pipeline:
    classify → fetch thread → generate reply → save draft.
    Returns True if a draft was created.
    """
    from classifier import classify_email
    from ai_engine import generate_reply

    email_id = email.get("id", "")

    # Skip already-processed emails
    if email_id in processed_ids:
        return False

    print(f"\n   📨  {email.get('subject', '(No Subject)')[:65]}")
    print(f"       From: {email.get('sender_name', '')} <{email.get('sender', '')}>")

    # Skip no-reply / automated senders
    if should_skip_sender(email, config):
        print(f"       ⏭️   Skipped (no-reply sender)")
        processed_ids.add(email_id)
        return False

    # ── Step 1: Classify ──────────────────────────────────────────────────
    classification = classify_email(email, config)
    if config.get("_ai_provider_used"):
        classification["ai_provider"] = config["_ai_provider_used"]
    if config.get("_ai_provider_fallback"):
        classification["ai_provider_fallback"] = True
        log_activity(
            "ai_provider_fallback",
            step="classification",
            from_provider=config.get("ai", {}).get("model", "openai"),
            to_provider=config.get("_ai_provider_used"),
            email_id=email_id,
            subject=email.get("subject", "")[:120],
        )
        worker_state.update("checking", ai_last_error=config.get("_ai_provider_error"), ai_fallback_provider=config.get("_ai_provider_used"))
        persist_provider_switch_if_needed(config, email, "classification")
    priority = classification.get("priority", "medium")
    category = classification.get("category", "other")
    needs_reply = classification.get("needs_reply", True)

    print(f"       📊  {category} | {priority} priority | needs_reply={needs_reply}")
    print(f"       💬  \"{classification.get('summary', '')}\"")
    log_activity(
        "email_classified",
        platform=platform,
        email_id=email_id,
        subject=email.get("subject", "")[:120],
        sender=email.get("sender", "")[:160],
        category=category,
        priority=priority,
        needs_reply=needs_reply,
    )

    skip_cats = config.get("filters", {}).get("skip_categories", [])
    if category in skip_cats or not needs_reply:
        reason = f"category={category}" if category in skip_cats else "needs_reply=False"
        print(f"       🚫  Skipped ({reason})")
        processed_ids.add(email_id)
        save_processed(processed_ids)
        return False

    # ── Step 2: Fetch thread history (for context) ────────────────────────
    thread_history = []
    try:
        if platform == "outlook":
            from outlook.fetcher import fetch_thread_history
            thread_history = fetch_thread_history(
                service_or_token, email["thread_id"], exclude_id=email_id
            )
        if thread_history:
            print(f"       🧵  {len(thread_history)} previous message(s) in thread")
    except Exception as e:
        print(f"       ⚠️   Could not fetch thread: {e}")

    # ── Step 3: Generate AI reply ─────────────────────────────────────────
    print(f"       🧠  Generating AI reply...")
    try:
        reply_body = generate_reply(email, thread_history, config)
        if config.get("_ai_provider_used"):
            classification["ai_provider"] = config["_ai_provider_used"]
        if config.get("_ai_provider_fallback"):
            classification["ai_provider_fallback"] = True
            log_activity(
                "ai_provider_fallback",
                step="generation",
                from_provider=config.get("ai", {}).get("model", "openai"),
                to_provider=config.get("_ai_provider_used"),
                email_id=email_id,
                subject=email.get("subject", "")[:120],
            )
            worker_state.update("checking", ai_last_error=config.get("_ai_provider_error"), ai_fallback_provider=config.get("_ai_provider_used"))
            persist_provider_switch_if_needed(config, email, "generation")
        print(f"       ✍️   Reply preview: {reply_body[:80].replace(chr(10), ' ')}...")
        log_activity(
            "draft_generated",
            platform=platform,
            email_id=email_id,
            subject=email.get("subject", "")[:120],
            sender=email.get("sender", "")[:160],
        )
    except Exception as e:
        print(f"       ❌  AI generation failed: {e}")
        print("       🔁  Will retry this email on the next check")
        log_activity(
            "ai_generation_failed",
            platform=platform,
            email_id=email_id,
            subject=email.get("subject", "")[:120],
            sender=email.get("sender", "")[:160],
            error=str(e),
        )
        worker_state.update("ai_error", ai_last_error=str(e), mailboxes={platform: "connected"})
        return False

    # ── Step 4: Save as platform draft ────────────────────────────────────
    platform_draft_id = None
    try:
        if platform == "outlook":
            from outlook.draft import create_draft
            platform_draft_id = create_draft(service_or_token, email, reply_body)
            print(f"       📝  Saved as Outlook draft")
    except Exception as e:
        print(f"       ⚠️   Could not save platform draft: {e}")
        print(f"            (Draft still logged locally for dashboard review)")

    # ── Step 5: Record in local draft store ───────────────────────────────
    draft_id = add_draft(drafts, email, reply_body, platform_draft_id, classification)
    print(f"       ✅  Logged → ID: {draft_id[:8]}...")
    log_activity(
        "draft_saved",
        draft_id=draft_id,
        platform=platform,
        subject=email.get("subject", "")[:120],
        sender=email.get("sender", "")[:160],
        provider_draft_created=bool(platform_draft_id),
    )

    if eligible_for_auto_send(classification, config) and platform_draft_id:
        from delivery import send_reply
        try:
            with draft_transaction(DRAFTS_FILE):
                latest = load_drafts()
                draft = latest[draft_id]
                # A user action between creation and sending always takes priority.
                if (draft['status'] == 'pending' and not draft.get('edited')
                        and not draft.get('links') and not draft.get('attachments')
                        and eligible_for_auto_send(classification, load_config())):
                    from outlook.auth import get_outlook_token
                    send_reply(draft, get_outlook_token)
                    draft['status'] = 'approved'
                    draft['approved_at'] = datetime.now().isoformat()
                    draft['auto_sent'] = True
                    save_drafts(latest)
                    log_activity("draft_auto_sent", draft_id=draft_id, platform=platform, subject=email.get("subject", "")[:120])
        except Exception as err:
            print(f"       ⚠️  Auto-send failed ({err}); queued in retry register.")
            try:
                import storage
                queue = storage.get_retry_queue()
                queue = [item for item in queue if item.get("draft_id") != draft_id]
                queue.append({
                    "draft_id": draft_id,
                    "subject": email.get("subject", ""),
                    "sender": email.get("sender", ""),
                    "attempt": 1,
                    "max_attempts": config.get("agent", {}).get("retry_max_attempts", 3),
                    "error": str(err),
                    "timestamp": datetime.now().isoformat(),
                    "platform": platform
                })
                storage.save_retry_queue(queue)
            except Exception:
                pass

    # ── Step 6: Mark original email as read ───────────────────────────────
    try:
        if platform == "outlook":
            from outlook.fetcher import mark_as_read
            mark_as_read(service_or_token, email_id)
    except Exception:
        pass

    processed_ids.add(email_id)
    save_processed(processed_ids)
    return True


# ─── Main Agent Loop ───────────────────────────────────────────────────────

def eligible_for_auto_send(classification, config):
    confidence = classification.get('confidence')
    return bool(config.get('agent', {}).get('auto_approve', False)
        and isinstance(confidence, (int, float)) and not isinstance(confidence, bool)
        and config.get('agent', {}).get('confidence_threshold', .85) <= confidence <= 1
        and classification.get('auto_reply_safe') is True
        and classification.get('needs_reply') is True
        and classification.get('priority') in ('low', 'medium')
        and classification.get('sentiment') in ('neutral', 'positive')
        and classification.get('category') in ('question', 'follow_up', 'information'))


def process_retry_queue(config):
    import storage
    from delivery import send_reply, sync_reply
    queue = storage.get_retry_queue()
    if not queue:
        return
    max_attempts = config.get("agent", {}).get("retry_max_attempts", 3)
    remaining = []
    changed = False
    with draft_transaction(DRAFTS_FILE):
        drafts = load_drafts()
        for item in queue:
            draft_id = item.get("draft_id")
            draft = drafts.get(draft_id)
            if not draft or draft.get("status") != "pending":
                changed = True
                continue
            attempts = int(item.get("attempt", 1))
            item["max_attempts"] = int(item.get("max_attempts") or max_attempts)
            if attempts >= item["max_attempts"] and item.get("exhausted"):
                remaining.append(item)
                continue
            classification = draft.get("classification") or {}
            if not eligible_for_auto_send(classification, config):
                item["error"] = "Auto-send settings no longer allow retry; review manually."
                item["exhausted"] = True
                remaining.append(item)
                changed = True
                continue
            try:
                from outlook.auth import get_outlook_token
                sync_reply(draft, get_outlook_token, [], lambda: save_drafts(drafts))
                send_reply(draft, get_outlook_token)
                draft["status"] = "approved"
                draft["approved_at"] = datetime.now().isoformat()
                draft["auto_sent"] = True
                log_activity("draft_auto_send_retry_succeeded", draft_id=draft_id, platform=draft.get("platform"), subject=draft.get("subject", "")[:120])
                changed = True
            except Exception as error:
                item["attempt"] = attempts + 1
                item["error"] = str(error)
                item["timestamp"] = datetime.now().isoformat()
                item["exhausted"] = item["attempt"] >= item["max_attempts"]
                remaining.append(item)
                log_activity("draft_auto_send_retry_failed", draft_id=draft_id, platform=draft.get("platform"), attempt=item["attempt"], error=str(error))
                changed = True
        if changed:
            save_drafts(drafts)
            storage.save_retry_queue(remaining)


def run_agent():
    log_activity("app_start")
    worker_state.update('starting')
    try:
        _run_agent()
    finally:
        log_activity("app_stop")
        worker_state.update('stopped')


def _run_agent():
    processed_ids = load_processed()
    while True:
        config = load_config()
        max_per = config.get('agent', {}).get('max_emails_per_check', 10)
        interval = max(30, config.get('agent', {}).get('check_interval_seconds', 120))
        from ai_engine import available_ai_providers
        if not available_ai_providers(config):
            worker_state.update('ai_key_required', mailboxes={})
            time.sleep(interval)
            continue
        statuses = {}
        log_activity("email_scan_started", providers=['outlook'] if config.get('platforms', {}).get('outlook', True) else [])
        worker_state.update('checking', mailboxes=statuses, ai_last_error=None, ai_fallback_provider=None)
        process_retry_queue(config)
        for provider in ('outlook',):
            # Re-read settings at each provider boundary; no cached enable flags.
            config = load_config()
            if not config.get('platforms', {}).get(provider, False):
                statuses[provider] = 'disabled'
                continue
            service = None
            try:
                from outlook.auth import get_outlook_token
                from outlook.fetcher import fetch_unread_outlook_emails
                service = get_outlook_token()
                emails = fetch_unread_outlook_emails(service, top=max_per, exclude_ids=processed_ids)
                statuses[provider] = 'connected'
                log_activity("email_scan_completed", provider=provider, count=len(emails))
                for email in emails:
                    if not load_config().get('platforms', {}).get(provider, False):
                        statuses[provider] = 'disabled'
                        break
                    process_email(email, provider, service, config, load_drafts(), processed_ids)
            except Exception:
                statuses[provider] = 'connection_error'
                log_activity("email_scan_failed", provider=provider)
                print(f'{provider}: connection or processing failed; check setup and provider access.')
            finally:
                worker_state.update('checking', mailboxes=dict(statuses))
        phase = 'connection_error' if 'connection_error' in statuses.values() else 'idle'
        worker_state.update(phase, mailboxes=dict(statuses))
        time.sleep(interval)


if __name__ == "__main__":
    run_agent()
