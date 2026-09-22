import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

import yaml

from api import server


class OutlookDashboardRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        self.drafts=root/"drafts.json"
        self.draft={"id":"d1","status":"pending","platform":"outlook","platform_draft_id":"remote",
            "email_id":"email","thread_id":"thread","subject":"Test","sender":"sender@example.com",
            "ai_reply":"Reviewed reply","original_body":"Original","attachments":[],"links":[]}
        self.drafts.write_text(json.dumps({"d1":self.draft}),encoding="utf-8")
        for patcher in (patch.object(server,"DRAFTS_FILE",self.drafts),
                        patch.object(server,"load_config",return_value={"agent":{"pin_security":False}}),
                        patch.dict(os.environ,{"DASHBOARD_PIN_SECURITY":"","DASHBOARD_PIN_HASH":"","DASHBOARD_PIN":""})):
            patcher.start(); self.addCleanup(patcher.stop)
        self.client=server.app.test_client()

    def test_non_outlook_mailbox_route_is_removed(self):
        self.assertEqual(self.client.get("/api/inbox/legacy-provider").status_code,404)

    @patch("outlook.draft.update_draft_body",side_effect=RuntimeError("offline"))
    @patch.object(server,"get_outlook",return_value="token")
    def test_failed_edit_preserves_saved_reply(self, token, update):
        response=self.client.put("/api/drafts/d1/edit",json={"ai_reply":"New text"})
        self.assertEqual(response.status_code,502)
        saved=json.loads(self.drafts.read_text())["d1"]
        self.assertEqual(saved["ai_reply"],"Reviewed reply")

    def test_snooze_persists_to_draft_store(self):
        until=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
        response=self.client.put("/api/drafts/d1/snooze",json={"snoozed_until":until})
        self.assertEqual(response.status_code,200)
        saved=json.loads(self.drafts.read_text())["d1"]
        self.assertEqual(saved["snoozed_until"],until)


class ConfigRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        self.config=root/"config.yaml"
        self.env=root/".env"
        self.config.write_text(yaml.safe_dump({
            "ai":{"model":"openai"},
            "agent":{"check_interval_seconds":120,"auto_approve":False,"sound_fx":True,"pin_security":False,"theme":"cyan","vip_contacts":[]},
            "user_style":{"tone":"professional","name":"Your Name","instructions":""},
            "platforms":{"outlook":True},
        }),encoding="utf-8")
        for patcher in (patch.object(server,"CONFIG_FILE",self.config),
                        patch.object(server,"ENV_FILE",self.env),
                        patch.dict(os.environ,{"DASHBOARD_PIN_SECURITY":"","DASHBOARD_PIN_HASH":"","DASHBOARD_PIN":""})):
            patcher.start(); self.addCleanup(patcher.stop)
        self.client=server.app.test_client()

    def test_vip_contacts_are_saved_from_settings(self):
        response=self.client.put("/api/config",json={
            "ai":{"model":"openai"},
            "user_style":{"tone":"professional","name":"Bhagyaraj","instructions":""},
            "agent":{"check_interval_seconds":120,"auto_approve":False,"sound_fx":True,"pin_security":False,"theme":"cyan","vip_contacts":["boss@example.com","*@client.com"]},
            "platforms":{"outlook":True},
            "api_keys":{},
        })
        self.assertEqual(response.status_code,200)
        saved=yaml.safe_load(self.config.read_text(encoding="utf-8"))
        self.assertEqual(saved["agent"]["vip_contacts"],["boss@example.com","*@client.com"])


if __name__ == "__main__":
    unittest.main()
