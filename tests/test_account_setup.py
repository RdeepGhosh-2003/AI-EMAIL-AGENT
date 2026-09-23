import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api import server


class OutlookAccountSetupTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        for patcher in (
            patch.object(server, "load_config", return_value={"agent": {"pin_security": False}}),
            patch.object(server, "OUTLOOK_TOKEN_FILE", root / "outlook" / "token_cache.json"),
            patch.object(server, "ENV_FILE", root / ".env"),
            patch.dict(os.environ, {"AZURE_CLIENT_ID": "", "AZURE_TENANT_ID": "", "ALLOWED_OUTLOOK_DOMAINS": ""}),
            patch.dict(os.environ, {"DASHBOARD_PIN_SECURITY": "", "DASHBOARD_PIN_HASH": "", "DASHBOARD_PIN": ""}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = server.app.test_client()

    def test_status_exposes_only_outlook_without_secrets(self):
        payload = self.client.get("/api/accounts/status").get_json()
        self.assertEqual(set(payload), {"outlook"})
        self.assertFalse(payload["outlook"]["credentials_ready"])
        self.assertNotIn("client_id", payload["outlook"])

    def test_saves_microsoft_configuration_without_returning_client_id(self):
        response = self.client.post("/api/accounts/outlook/config", json={
            "client_id": "12345678-abcd-1234-abcd-123456789012", "tenant_id": "common"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("AZURE_CLIENT_ID", server.ENV_FILE.read_text())
        status = self.client.get("/api/accounts/status").get_json()
        self.assertTrue(status["outlook"]["credentials_ready"])
        self.assertNotIn("client_id", status["outlook"])

    def test_company_domain_requires_specific_tenant(self):
        with patch.dict(os.environ, {"ALLOWED_OUTLOOK_DOMAINS": "durgabrgs.com"}):
            response = self.client.post("/api/accounts/outlook/config", json={
                "client_id": "12345678-abcd-1234-abcd-123456789012", "tenant_id": "common"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Directory tenant ID", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
