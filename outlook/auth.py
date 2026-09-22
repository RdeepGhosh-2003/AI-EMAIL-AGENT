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
        try:
            if len(accounts) == 1 and not interactive:
                result = app.acquire_token_silent(GRAPH_SCOPES, account=accounts[0])
            if interactive:
                result = app.acquire_token_interactive(
                    scopes=GRAPH_SCOPES, prompt='select_account', timeout=300
                )
            if not result or 'access_token' not in result:
                raise RuntimeError(
                    'Outlook requires sign-in. Run: python connect_email.py outlook. '
                    'Choose the trial account and complete Microsoft consent.'
                )
            return result['access_token']
        finally:
            if cache.has_state_changed:
                temporary = TOKEN_PATH.with_suffix('.tmp')
                temporary.write_text(cache.serialize(), encoding='utf-8')
                temporary.replace(TOKEN_PATH)
