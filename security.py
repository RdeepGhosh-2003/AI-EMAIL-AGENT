"""Dashboard host checks and PIN-unlocked browser sessions."""
import hashlib
import hmac
import os
import secrets
import time
from flask import request, jsonify, session, redirect
from werkzeug.security import check_password_hash
from activity_log import log_activity


def credential_tag(settings):
    pin_hash = os.getenv('DASHBOARD_PIN_HASH', '')
    fallback = settings.get('pin_hash') or settings.get('pin_code', '')
    return hashlib.sha256(str(pin_hash or fallback).encode()).hexdigest()


def pin_security_enabled(settings):
    env_value = os.getenv('DASHBOARD_PIN_SECURITY')
    value = env_value if env_value not in (None, '') else settings.get('pin_security', False)
    return str(value).lower() in ('1', 'true', 'yes', 'on')


def configured_pin_valid(settings, supplied):
    pin_hash = os.getenv('DASHBOARD_PIN_HASH', '').strip()
    plain_pin = os.getenv('DASHBOARD_PIN', '').strip()
    if pin_hash:
        return check_password_hash(pin_hash, supplied)
    if plain_pin:
        return hmac.compare_digest(plain_pin, supplied)
    if settings.get('pin_hash'):
        return check_password_hash(settings['pin_hash'], supplied)
    if settings.get('pin_code'):
        return hmac.compare_digest(str(settings['pin_code']), supplied)
    return False


def host_allowed(hostname):
    allowed = {'localhost', '127.0.0.1'}
    extra = os.getenv('DASHBOARD_ALLOWED_HOSTS', '')
    allowed.update(item.strip().lower() for item in extra.split(',') if item.strip())
    return (hostname or '').lower() in allowed


def unlocked(settings):
    return (
        session.get('pin_tag') == credential_tag(settings) and
        time.time() - session.get('unlocked_at', 0) < 1800
    )


def install_security(app, load_config):
    app.secret_key = secrets.token_hex(32)
    secure_cookie = str(os.getenv('DASHBOARD_COOKIE_SECURE', '')).lower() in ('1', 'true', 'yes', 'on')
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Strict',
        SESSION_COOKIE_SECURE=secure_cookie,
    )
    attempts = {}

    @app.before_request
    def guard():
        if request.path.startswith('/static/'):
            return
        settings = load_config().get('agent', {})
        security_on = pin_security_enabled(settings)
        host = request.host.split(':')[0]
        if not host_allowed(host):
            log_activity('dashboard_host_blocked', host=host, path=request.path, remote_addr=request.remote_addr)
            if request.path.startswith('/api/'):
                return jsonify(error='Open the dashboard through localhost or an allowed private host.'), 403
            return 'Open the dashboard through localhost or an allowed private host.', 403
        if request.headers.get('Origin') not in (None, request.host_url.rstrip('/')):
            log_activity('dashboard_origin_blocked', path=request.path, remote_addr=request.remote_addr)
            return jsonify(error='Cross-origin API access is not allowed.'), 403
        if request.path in ('/login', '/api/unlock', '/api/auth/status'):
            return
        if not security_on:
            return
        if not unlocked(settings):
            if request.path.startswith('/api/'):
                return jsonify(error='Unlock the dashboard with your PIN.', code='PIN_REQUIRED'), 401
            return redirect('/login')

    @app.get('/api/auth/status')
    def auth_status():
        settings = load_config().get('agent', {})
        security_on = pin_security_enabled(settings)
        return jsonify(pin_security=security_on, unlocked=(not security_on or unlocked(settings)))

    @app.post('/api/unlock')
    def unlock():
        settings = load_config().get('agent', {})
        key = request.remote_addr
        failures, last = attempts.get(key, (0, 0))
        if failures >= 5 and time.monotonic() - last < 60:
            return jsonify(error='Too many incorrect PINs. Try again in one minute.'), 429
        supplied = (request.get_json(silent=True) or {}).get('pin', '')
        supplied = supplied if isinstance(supplied, str) else ''
        valid = configured_pin_valid(settings, supplied)
        if pin_security_enabled(settings) and not valid:
            attempts[key] = (failures + 1 if time.monotonic() - last < 60 else 1, time.monotonic())
            log_activity('dashboard_login_failed', remote_addr=request.remote_addr)
            return jsonify(error='Incorrect PIN.'), 401
        attempts.pop(key, None)
        session['pin_tag'] = credential_tag(settings)
        session['unlocked_at'] = time.time()
        session.permanent = False
        log_activity('dashboard_login_success', remote_addr=request.remote_addr)
        return jsonify(success=True)

    @app.post('/api/logout')
    def logout():
        session.clear()
        log_activity('dashboard_logout', remote_addr=request.remote_addr)
        return jsonify(success=True)
