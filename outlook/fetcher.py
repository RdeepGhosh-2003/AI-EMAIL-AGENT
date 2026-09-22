"""
outlook/fetcher.py — Fetch unread emails and thread history from Outlook
via Microsoft Graph API.
"""

import re
import requests
from bs4 import BeautifulSoup

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def fetch_unread_outlook_emails(token: str, top: int = 10, exclude_ids=None) -> list:
    """
    Fetches unread emails from the Outlook inbox.
    Returns a list of normalized email dicts.
    """
    headers = _auth_headers(token)
    url = f"{GRAPH_BASE}/me/mailFolders/inbox/messages"
    params = {
        "$filter": "isRead eq false",
        "$top": min(100, max(25, top * 3)),
        "$select": "id,subject,from,body,bodyPreview,receivedDateTime,conversationId,toRecipients",
        "$orderby": "receivedDateTime desc",
    }

    exclude_ids = set(exclude_ids or ())
    messages = []
    scanned = 0
    next_url = url
    next_params = params
    while next_url and len(messages) < top and scanned < 500:
        resp = requests.get(next_url, headers=headers, params=next_params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        page = data.get("value", [])
        scanned += len(page)
        messages.extend(m for m in page if m["id"] not in exclude_ids)
        next_url = data.get("@odata.nextLink")
        next_params = None

    return [_parse_message(m) for m in messages[:top]]


def fetch_thread_history(token: str, conversation_id: str, exclude_id: str = None) -> list:
    """
    Fetches the conversation thread for context.
    """
    headers = _auth_headers(token)
    url = f"{GRAPH_BASE}/me/messages"
    params = {
        "$filter": f"conversationId eq '{conversation_id}'",
        "$select": "id,subject,from,body,receivedDateTime",
        "$orderby": "receivedDateTime asc",
        "$top": 10,
    }

    resp = requests.get(url, headers=headers, params=params, timeout=15)
    if not resp.ok:
        return []

    messages = [_parse_message(m) for m in resp.json().get("value", [])]
    return [m for m in messages if m["id"] != exclude_id]


def mark_as_read(token: str, message_id: str):
    """Marks an Outlook message as read."""
    try:
        headers = _auth_headers(token)
        url = f"{GRAPH_BASE}/me/messages/{message_id}"
        requests.patch(url, headers=headers, json={"isRead": True}, timeout=10)
    except Exception:
        pass


def _parse_message(msg: dict) -> dict:
    """Normalizes a Microsoft Graph message to shared schema."""
    body_content = msg.get("body", {}).get("content", "")
    body_type = msg.get("body", {}).get("contentType", "text")

    if body_type == "html":
        try:
            body_text = _html_to_text(body_content)
        except Exception:
            body_text = msg.get("bodyPreview", "")
    else:
        body_text = body_content.strip()

    sender_info = msg.get("from", {}).get("emailAddress", {})

    return {
        "id": msg["id"],
        "thread_id": msg.get("conversationId", ""),
        "subject": msg.get("subject", "(No Subject)"),
        "sender": sender_info.get("address", ""),
        "sender_name": sender_info.get("name", ""),
        "body": body_text,
        "date": msg.get("receivedDateTime", ""),
        "platform": "outlook",
    }


def _html_to_text(content: str) -> str:
    """Convert Outlook HTML without splitting every inline element onto a new line."""
    soup = BeautifulSoup(content or "", "html.parser")
    for element in soup(("script", "style", "head", "img")):
        element.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for element in soup.find_all(("p", "div", "li", "tr", "blockquote")):
        element.append("\n")
    for element in soup.find_all(("td", "th")):
        element.append(" ")
    text = soup.get_text(" ").replace("\xa0", " ")
    text = re.sub(r"\[cid:[^\]]+\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _auth_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
