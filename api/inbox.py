"""Read-only mailbox endpoints. Reading here never marks messages as read."""
from pathlib import Path
from flask import Blueprint, jsonify, request
import requests
from security import host_allowed

inbox = Blueprint('inbox', __name__)
ROOT = Path(__file__).resolve().parents[1]


@inbox.before_request
def local_only():
    if not host_allowed(request.host.split(':')[0]):
        return jsonify(error='Open the inbox through localhost or an allowed private host.'), 403
    if request.headers.get('Origin') not in (None, request.host_url.rstrip('/')):
        return jsonify(error='Cross-origin mailbox access is not allowed.'), 403


@inbox.route('/api/inbox/<provider>')
def messages(provider):
    if provider != 'outlook':
        return jsonify(error='Unknown mailbox'), 404
    message_id = request.args.get('id')
    try:
        if not (ROOT / 'outlook/token_cache.json').exists():
            return jsonify(error='Outlook needs sign-in. Run python connect_email.py outlook, then Refresh. Your organization may require administrator approval.'), 401
        from outlook.auth import get_outlook_token
        from outlook.fetcher import _parse_message
        from urllib.parse import quote
        headers = {'Authorization': 'Bearer ' + get_outlook_token(), 'Prefer': 'outlook.body-content-type="text"'}
        base = 'https://graph.microsoft.com/v1.0/me'
        if message_id:
            response = requests.get(base + '/messages/' + quote(message_id, safe=''), headers=headers, timeout=20)
            response.raise_for_status()
            return jsonify(message=_parse_message(response.json()))
        try:
            page = max(0, int(request.args.get('page', 0)))
        except ValueError:
            return jsonify(error='Invalid page. Choose Newest to restart.'), 400
        response = requests.get(base + '/mailFolders/inbox/messages', headers=headers, timeout=20,
            params={'$top': 20, '$skip': page, '$orderby': 'receivedDateTime desc',
                    '$select': 'id,subject,from,bodyPreview,receivedDateTime,isRead'})
        response.raise_for_status()
        result = response.json()
        return jsonify(messages=[dict(_parse_message(m), preview=m.get('bodyPreview', ''), unread=not m.get('isRead')) for m in result.get('value', [])],
                       next_page=str(page + 20) if result.get('@odata.nextLink') else None)
    except Exception as error:
        from mailbox_errors import describe
        message, status = describe(error, provider)
        return jsonify(error=message), status
