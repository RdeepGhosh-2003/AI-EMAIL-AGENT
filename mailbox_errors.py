"""Safe, actionable mailbox errors without credentials or email contents."""
def describe(error, provider):
    status = getattr(getattr(error, 'resp', None), 'status', None)
    if status is None:
        response = getattr(error, 'response', None)
        status = getattr(response, 'status_code', None)
    name = type(error).__name__
    if name == 'RefreshError' or status == 401 or isinstance(error, (FileNotFoundError, RuntimeError)):
        return f'{provider.title()} needs sign-in. Run python connect_email.py {provider}, then Refresh.', 401
    if status == 403:
        return f'{provider.title()} denied mailbox access. Check account permissions and provider policy; administrator approval may be required.', 403
    if status == 404:
        return 'This message is no longer available. Refresh the inbox.', 404
    if status == 429:
        return 'The email provider is rate limiting requests. Wait and try Refresh.', 429
    return f'Could not reach {provider.title()}. Check your network or proxy and try Refresh. If it persists, reconnect the account.', 502
