import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from outlook import auth


class OutlookAuthTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'cache.json'
        for patcher in (
            patch.object(auth, 'TOKEN_PATH', self.path),
            patch.dict(os.environ, {'AZURE_CLIENT_ID': 'test-id', 'AZURE_TENANT_ID': '', 'ALLOWED_OUTLOOK_DOMAINS': ''}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.factory = patch.object(auth.msal, 'PublicClientApplication').start()
        self.addCleanup(patch.stopall)
        self.app = self.factory.return_value
        self.app.get_accounts.return_value = []

    def test_background_does_not_open_sign_in(self):
        with self.assertRaisesRegex(RuntimeError, 'connect_email.py outlook'):
            auth.get_outlook_token()
        self.app.acquire_token_interactive.assert_not_called()

    def test_cached_account_uses_delegated_scopes(self):
        account = {'home_account_id': 'test'}
        self.app.get_accounts.return_value = [account]
        self.app.acquire_token_silent.return_value = {'access_token': 'test-token'}
        self.assertEqual(auth.get_outlook_token(), 'test-token')
        self.app.acquire_token_silent.assert_called_once_with(
            ['Mail.ReadWrite', 'Mail.Send'], account=account
        )
        self.app.acquire_token_interactive.assert_not_called()

    def test_company_domain_account_is_allowed(self):
        account = {'home_account_id': 'test', 'username': 'pc@durgabrgs.com'}
        self.app.get_accounts.return_value = [account]
        self.app.acquire_token_silent.return_value = {'access_token': 'test-token'}
        with patch.dict(os.environ, {'ALLOWED_OUTLOOK_DOMAINS': 'durgabrgs.com'}):
            self.assertEqual(auth.get_outlook_token(), 'test-token')

    def test_non_company_domain_account_is_blocked(self):
        account = {'home_account_id': 'test', 'username': 'someone@example.com'}
        self.app.get_accounts.return_value = [account]
        self.app.acquire_token_silent.return_value = {'access_token': 'test-token'}
        with patch.dict(os.environ, {'ALLOWED_OUTLOOK_DOMAINS': 'durgabrgs.com'}):
            with self.assertRaisesRegex(PermissionError, 'Only company Outlook accounts'):
                auth.get_outlook_token()

    def test_explicit_setup_and_persistence(self):
        def authorize(**kwargs):
            cache = self.factory.call_args.kwargs['token_cache']
            cache.has_state_changed = True
            return {'access_token': 'test-token', 'id_token_claims': {'preferred_username': 'pc@durgabrgs.com'}}
        self.app.acquire_token_interactive.side_effect = authorize
        with patch.dict(os.environ, {'ALLOWED_OUTLOOK_DOMAINS': 'durgabrgs.com'}):
            self.assertEqual(auth.get_outlook_token(interactive=True), 'test-token')
        self.assertTrue(self.path.exists())
        self.assertFalse(self.path.with_suffix('.tmp').exists())
        self.assertEqual(
            self.factory.call_args.kwargs['authority'],
            'https://login.microsoftonline.com/common',
        )

    def test_multiple_cached_accounts_require_selection(self):
        self.app.get_accounts.return_value = [{'id': 'a'}, {'id': 'b'}]
        with self.assertRaises(RuntimeError):
            auth.get_outlook_token()
        self.app.acquire_token_silent.assert_not_called()

    def test_missing_client_id_fails_before_network(self):
        with patch.dict(os.environ, {'AZURE_CLIENT_ID': ''}):
            with self.assertRaises(EnvironmentError):
                auth.get_outlook_token()
        self.factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
