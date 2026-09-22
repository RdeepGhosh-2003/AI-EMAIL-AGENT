import unittest

from ai_engine import _build_prompt
from outlook.fetcher import _parse_message


class OutlookFormattingTests(unittest.TestCase):
    def test_inline_signature_content_stays_on_normal_lines(self):
        message = _parse_message({
            "id": "1",
            "subject": "Payment",
            "from": {"emailAddress": {"name": "Bishnu", "address": "bishnu@example.com"}},
            "body": {"contentType": "html", "content": (
                "<p>Dear Sneha,</p><p>Are you handling this payment?</p>"
                "<div>With Best Regards<br>Bishnu Sultania<br>Director<br>"
                "10/26C, WOC Road, <span>1st R Block</span>, Rajajinagar<br>"
                "T <span>+91-80-67718009</span><br>E <a>bishnu@example.com</a><br>"
                "W <a>www.example.com</a><img src='cid:image003.jpg'></div>")},
        })
        body = message["body"]
        self.assertIn("1st R Block", body)
        self.assertIn("T +91-80-67718009", body)
        self.assertIn("E bishnu@example.com", body)
        self.assertNotIn("\n1\nst", body)
        self.assertNotIn("cid:", body)

    def test_blank_profile_forbids_generated_sender_name(self):
        prompt = _build_prompt({"sender":"a@example.com","body":"Hello"}, [], {
            "user_style":{"name":"","signature":"","tone":"professional"}})
        self.assertIn("Do not add a closing sign-off, sender name, or signature", prompt)
        self.assertIn("Your name: not configured", prompt)


if __name__ == "__main__":
    unittest.main()
