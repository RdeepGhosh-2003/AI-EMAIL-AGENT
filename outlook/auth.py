"""
outlook/auth.py — Microsoft Graph API authentication via MSAL.
Uses delegated user sign-in so Microsoft Graph /me endpoints work.
"""

import os
from pathlib import Path
from threading import Lock
import msal
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

GRAPH_SCOPES = ['Mail.ReadWrite', 'Mail.Send']
TOKEN_PATH = ROOT / 'outlook' / 'token_cache.json'
_LOCK = Lock()


def allowed_outlook_domains() -> list[str]:
    raw = os.getenv('ALLOWED_OUTLOOK_DOMAINS', os.getenv('ALLOWED_OUTLOOK_DOMAIN', '')).strip()
    return [item.strip().lower().lstrip('@') for item in raw.split(',') if item.strip()]


def account_email(result: dict, account: dict | None = None) -> str:
    claims = result.get('id_token_claims') or {}
    for value in (
        claims.get('preferred_username'),
        claims.get('email'),
        claims.get('upn'),
        (account or {}).get('username'),
    ):
        if value:
            return str(value).strip().lower()
    return ''


def validate_allowed_account(result: dict, account: dict | None = None) -> None:
    domains = allowed_outlook_domains()
    if not domains:
        return
    email = account_email(result, account)
    if not email or '@' not in email:
        raise PermissionError(
            'Could not confirm the signed-in Outlook email address. '
            'Sign in again with your company Outlook account.'
        )
    domain = email.rsplit('@', 1)[1]
    if domain not in domains:
        allowed = ', '.join('@' + item for item in domains)
        raise PermissionError(f'Only company Outlook accounts are allowed here. Sign in with {allowed}.')


def get_outlook_token(interactive: bool = False) -> str:
    """
    Reuse or refresh saved credentials. Interactive sign-in is explicit setup only.
    Register a desktop app with http://localhost redirect URI and delegated
    Mail.ReadWrite and Mail.Send permissions, then set AZURE_CLIENT_ID in .env.
    """
    client_id = os.getenv('AZURE_CLIENT_ID', '').strip()
    tenant_id = os.getenv('AZURE_TENANT_ID', '').strip() or 'common'

    if not client_id:
        raise EnvironmentError(
            "\n❌ Outlook credentials missing in .env!\n"
            "   Set AZURE_CLIENT_ID in .env, then run python connect_email.py outlook\n"
            "   See README.md → Outlook Setup for instructions.\n"
        )

    with _LOCK:
        cache = msal.SerializableTokenCache()
        if TOKEN_PATH.exists():
            cache.deserialize(TOKEN_PATH.read_text(encoding='utf-8'))
        app = msal.PublicClientApplication(
            client_id,
            authority=f'https://login.microsoftonline.com/{tenant_id}',
            token_cache=cache,
        )
        accounts = app.get_accounts()
        result = None
        selected_account = accounts[0] if len(accounts) == 1 and not interactive else None
        try:
            if selected_account:
                result = app.acquire_token_silent(GRAPH_SCOPES, account=selected_account)
            if interactive:
                result = app.acquire_token_interactive(
                    scopes=GRAPH_SCOPES, prompt='select_account', timeout=300
                )
            if not result or 'access_token' not in result:
                raise RuntimeError(
                    'Outlook requires sign-in. Run: python connect_email.py outlook. '
                    'Choose the trial account and complete Microsoft consent.'
                )
            validate_allowed_account(result, selected_account)
            return result['access_token']
        finally:
            if cache.has_state_changed:
                temporary = TOKEN_PATH.with_suffix('.tmp')
                temporary.write_text(cache.serialize(), encoding='utf-8')
                temporary.replace(TOKEN_PATH)
