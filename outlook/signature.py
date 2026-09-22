"""Discover and render the connected user's Classic Outlook reply signature."""

import base64
import hashlib
import html
import json
import mimetypes
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup


def account_from_token(token: str) -> str:
    """Read the signed-in address claim. This is an identity hint, not auth validation."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
    except (ValueError, IndexError, UnicodeDecodeError, json.JSONDecodeError):
        return ""
    return str(claims.get("preferred_username") or claims.get("upn") or claims.get("email") or "").strip().lower()


def signature_root() -> Path:
    appdata = os.getenv("APPDATA", "").strip()
    return Path(appdata) / "Microsoft" / "Signatures" if appdata else Path("__missing_outlook_signatures__")


def cached_account(cache_path: Path | None = None) -> str:
    """Read the username MSAL already stores locally, without a network refresh."""
    cache_path = cache_path or Path(__file__).with_name("token_cache.json")
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        accounts = list((cache.get("Account") or {}).values())
        return str(accounts[0].get("username") or "").strip().lower() if len(accounts) == 1 else ""
    except (OSError, ValueError, AttributeError):
        return ""


def find_reply_signature(account: str, root: Path | None = None) -> Path | None:
    """Return only a reply signature explicitly belonging to account; never cross accounts."""
    account = account.strip().lower()
    root = root or signature_root()
    if not account or not root.is_dir():
        return None
    candidates = [p for p in root.glob("*.htm") if account in p.stem.lower()]
    reply = [p for p in candidates if re.search(r"(^|[ _(-])repl(y|ies)([ _)\-]|$)", p.stem, re.I)]
    return sorted(reply or candidates, key=lambda p: p.name.lower())[0] if (reply or candidates) else None


def load_signature(account: str, root: Path | None = None) -> dict:
    path = find_reply_signature(account, root)
    if not path:
        return {"available": False, "account": account, "name": "", "html": "", "attachments": []}

    raw = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup.find_all(["script", "object", "embed", "meta"]):
        tag.decompose()

    attachments = []
    seen = set()
    safe_root = (root or signature_root()).resolve()
    for image in soup.find_all("img", src=True):
        source = unquote(urlparse(image["src"]).path).replace("/", os.sep)
        candidate = (path.parent / source).resolve()
        try:
            candidate.relative_to(safe_root)
        except ValueError:
            continue
        if not candidate.is_file():
            continue
        data = candidate.read_bytes()
        digest = hashlib.sha256(data).hexdigest()[:24]
        content_id = f"ai-agent-signature-{digest}"
        image["src"] = f"cid:{content_id}"
        if content_id in seen:
            continue
        seen.add(content_id)
        attachments.append({
            "name": candidate.name,
            "content_type": mimetypes.guess_type(candidate.name)[0] or "application/octet-stream",
            "data": data,
            "content_id": content_id,
        })

    styles = "".join(str(tag) for tag in soup.head.find_all("style")) if soup.head else ""
    body = "".join(str(node) for node in (soup.body.contents if soup.body else soup.contents))
    return {
        "available": True,
        "account": account,
        "name": path.stem,
        "html": styles + body,
        "attachments": attachments,
    }


def compose_reply(token: str, reply_body: str, root: Path | None = None) -> tuple[str, dict]:
    account = account_from_token(token)
    signature = load_signature(account, root)
    reply_html = '<div style="white-space:normal">' + html.escape(reply_body).replace("\n", "<br>") + "</div>"
    if signature["available"]:
        reply_html += '<div style="margin-top:18px">' + signature["html"] + "</div>"
    return reply_html, signature


def signature_status(token: str, root: Path | None = None) -> dict:
    account = account_from_token(token)
    found = find_reply_signature(account, root)
    return {"available": bool(found), "account": account, "name": found.stem if found else ""}


def cached_signature_status(root: Path | None = None, cache_path: Path | None = None) -> dict:
    account = cached_account(cache_path)
    found = find_reply_signature(account, root)
    return {"available": bool(found), "account": account, "name": found.stem if found else ""}
