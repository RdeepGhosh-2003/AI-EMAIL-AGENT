import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from outlook.signature import account_from_token, cached_account, compose_reply, find_reply_signature, load_signature


def token_for(address):
    payload = base64.urlsafe_b64encode(json.dumps({"preferred_username": address}).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


class OutlookSignatureTests(unittest.TestCase):
    def test_reads_connected_username_from_msal_cache_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "token_cache.json"
            cache.write_text(json.dumps({"Account": {"key": {"username": "PC@Example.com"}}}), encoding="utf-8")
            self.assertEqual(cached_account(cache), "pc@example.com")

    def test_selects_only_signature_for_connected_account(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Reply (mis@example.com).htm").write_text("MIS", encoding="utf-8")
            self.assertEqual(find_reply_signature("pc@example.com", root).name, "Reply (mis@example.com).htm")
            (root / "Reply (pc@example.com).htm").write_text("PC", encoding="utf-8")
            self.assertEqual(find_reply_signature("pc@example.com", root).name, "Reply (pc@example.com).htm")

    def test_does_not_guess_when_multiple_unmatched_signatures_exist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Sales.htm").write_text("Sales", encoding="utf-8")
            (root / "Support.htm").write_text("Support", encoding="utf-8")
            self.assertIsNone(find_reply_signature("pc@example.com", root))

    def test_rewrites_local_images_as_inline_cid_attachments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / "Reply (pc@example.com)_files"
            assets.mkdir()
            (assets / "logo.png").write_bytes(b"fake-png")
            (root / "Reply (pc@example.com).htm").write_text(
                '<html><body><b>PC Footer</b><img src="Reply%20(pc@example.com)_files/logo.png"></body></html>',
                encoding="utf-8",
            )
            signature = load_signature("pc@example.com", root)
            self.assertTrue(signature["available"])
            self.assertIn("cid:ai-agent-signature-", signature["html"])
            self.assertEqual(signature["attachments"][0]["data"], b"fake-png")

    def test_composes_escaped_reply_and_matching_signature(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Reply (pc@example.com).htm").write_text("<html><body>My Footer</body></html>", encoding="utf-8")
            body, signature = compose_reply(token_for("pc@example.com"), "Hello <team>\nThanks", root)
            self.assertEqual(account_from_token(token_for("pc@example.com")), "pc@example.com")
            self.assertIn("Hello &lt;team&gt;<br>Thanks", body)
            self.assertIn("My Footer", body)
            self.assertTrue(signature["available"])

    @patch("outlook.draft.compose_reply")
    @patch("outlook.draft.requests")
    def test_draft_uses_html_and_does_not_duplicate_inline_image(self, requests, compose):
        from outlook.draft import update_draft_body
        compose.return_value = ("<div>Reply</div>", {"attachments": [{
            "name": "logo.png", "content_type": "image/png", "data": b"png", "content_id": "cid-1"
        }]})
        listing = Mock()
        listing.json.return_value = {"value": [{"isInline": True, "contentId": "cid-1"}]}
        requests.get.return_value = listing
        requests.patch.return_value = Mock()

        update_draft_body("token", "draft", "Reply")

        requests.post.assert_not_called()
        payload = requests.patch.call_args.kwargs["json"]
        self.assertEqual(payload["body"]["contentType"], "HTML")


if __name__ == "__main__":
    unittest.main()
