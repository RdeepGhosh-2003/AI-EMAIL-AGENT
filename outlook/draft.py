"""
outlook/draft.py — Create, send, and delete Outlook draft replies
via Microsoft Graph API.
"""

import requests
import base64

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def create_draft(token: str, original_email: dict, reply_body: str) -> str:
    """
    Creates a draft reply for an Outlook email.
    Returns the Microsoft Graph draft message ID.
    """
    headers = _auth_headers(token)

    # Step 1: Create a reply draft linked to the original thread
    create_url = f"{GRAPH_BASE}/me/messages/{original_email['id']}/createReply"
    resp = requests.post(create_url, headers=headers, timeout=15)
    resp.raise_for_status()
    draft_id = resp.json()["id"]

    # Step 2: Patch the draft with our AI-generated reply body
    update_url = f"{GRAPH_BASE}/me/messages/{draft_id}"
    payload = {
        "body": {
            "contentType": "Text",
            "content": reply_body,
        }
    }
    updated = requests.patch(update_url, headers=headers, json=payload, timeout=15)
    updated.raise_for_status()

    return draft_id


def send_draft(token: str, draft_id: str):
    """Sends a saved Outlook draft (called when user approves from dashboard)."""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{GRAPH_BASE}/me/messages/{draft_id}/send"
    resp = requests.post(url, headers=headers, timeout=15)
    resp.raise_for_status()


def add_attachments_to_draft(token: str, draft_id: str, attachments: list):
    """Add small files of any type to an existing Outlook draft."""
    headers = _auth_headers(token)
    url = f"{GRAPH_BASE}/me/messages/{draft_id}/attachments"
    uploaded = []
    for item in attachments:
        response = requests.post(url, headers=headers, json={
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": item["name"],
            "contentType": item.get("content_type", "application/octet-stream"),
            "contentBytes": base64.b64encode(item["data"]).decode("ascii"),
        }, timeout=30)
        response.raise_for_status()
        uploaded.append(response.json()["id"])
    return uploaded


def remove_attachment(token, draft_id, attachment_id):
    response = requests.delete(f"{GRAPH_BASE}/me/messages/{draft_id}/attachments/{attachment_id}",
        headers=_auth_headers(token), timeout=15)
    if response.status_code not in (404, 410):
        response.raise_for_status()


def update_draft_body(token: str, draft_id: str, reply_body: str):
    response = requests.patch(
        f"{GRAPH_BASE}/me/messages/{draft_id}",
        headers=_auth_headers(token),
        json={"body": {"contentType": "Text", "content": reply_body}},
        timeout=15,
    )
    response.raise_for_status()


def delete_draft(token: str, draft_id: str):
    """Deletes an Outlook draft (called when user rejects from dashboard)."""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{GRAPH_BASE}/me/messages/{draft_id}"
    response = requests.delete(url, headers=headers, timeout=10)
    if response.status_code not in (404, 410):
        response.raise_for_status()


def _auth_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
