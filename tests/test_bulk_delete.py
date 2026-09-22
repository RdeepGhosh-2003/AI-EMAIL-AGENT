import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api import server


class OutlookBulkDeleteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.drafts_file = Path(self.temp_dir.name) / "drafts.json"
        self.draft = {"id":"local-1","subject":"Quarterly update","platform":"outlook",
            "platform_draft_id":"outlook-1","email_id":"email-1","thread_id":"thread-1",
            "sender":"sender@example.com","status":"pending","ai_reply":"Thanks.","attachments":[]}
        self.drafts_file.write_text(json.dumps({"local-1": self.draft}), encoding="utf-8")
        for patcher in (patch.object(server,"load_config",return_value={"agent":{"pin_security":False}}),
                        patch.object(server,"DRAFTS_FILE",self.drafts_file),
                        patch.dict(os.environ,{"DASHBOARD_PIN_SECURITY":"","DASHBOARD_PIN_HASH":"","DASHBOARD_PIN":""})):
            patcher.start(); self.addCleanup(patcher.stop)
        self.client = server.app.test_client()

    def saved(self):
        return json.loads(self.drafts_file.read_text())["local-1"]

    @patch("outlook.draft.delete_draft")
    @patch.object(server,"get_outlook",side_effect=ConnectionError("offline"))
    def test_provider_outage_does_not_block_local_delete(self, token, delete):
        response=self.client.post("/api/drafts/bulk-delete",json={"ids":["local-1"]})
        self.assertEqual(response.status_code,200)
        self.assertTrue(self.saved()["provider_cleanup_pending"])
        delete.assert_not_called()

    @patch("outlook.draft.create_draft",return_value="outlook-restored")
    @patch.object(server,"get_outlook",return_value="token")
    def test_deleted_draft_can_be_restored(self, token, create):
        saved={**self.draft,"status":"deleted","deleted_at":"2026-09-17T10:00:00"}
        self.drafts_file.write_text(json.dumps({"local-1":saved}),encoding="utf-8")
        response=self.client.post("/api/drafts/local-1/restore")
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.saved()["platform_draft_id"],"outlook-restored")


if __name__ == "__main__":
    unittest.main()
