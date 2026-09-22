"""Synchronize the reviewed reply before requesting delivery from the provider."""
from storage import is_demo


def email_stub(draft):
    return {"id": draft["email_id"], "thread_id": draft.get("thread_id", ""),
        "message_id": draft.get("message_id"), "sender": draft["sender"], "subject": draft.get("subject", "")}


def reply_with_links(draft):
    links = draft.get("links", [])
    return draft["ai_reply"] + ("\n\nLinks:\n" + "\n".join(
        f"- {link['label']}: {link['url']}" for link in links) if links else "")


def sync_reply(draft, outlook_factory, attachments=None, persist=lambda: None):
    if is_demo(draft):
        raise ValueError("Demo drafts cannot be synchronized or sent")
    provider = draft.get("platform")
    draft_id = draft.get("platform_draft_id")
    body = reply_with_links(draft)
    if provider == "outlook":
        from outlook.draft import create_draft, update_draft_body, add_attachments_to_draft
        token = outlook_factory()
        if not draft_id:
            draft_id = create_draft(token, email_stub(draft), body)
            draft["platform_draft_id"] = draft_id
            persist()
        else:
            update_draft_body(token, draft_id, body)
        for item in attachments or []:
            stored = next(entry for entry in draft["attachments"] if entry["id"] == item["id"])
            if not stored.get("provider_attachment_id"):
                stored["provider_attachment_id"] = add_attachments_to_draft(token, draft_id, [item])[0]
                persist()
    else:
        raise ValueError("Unsupported email provider")


def send_reply(draft, outlook_factory):
    if is_demo(draft) or not draft.get("platform_draft_id"):
        raise ValueError("A real provider draft is required before sending")
    if draft["platform"] == "outlook":
        from outlook.draft import send_draft
        send_draft(outlook_factory(), draft["platform_draft_id"])
    else:
        raise ValueError("Unsupported email provider")
