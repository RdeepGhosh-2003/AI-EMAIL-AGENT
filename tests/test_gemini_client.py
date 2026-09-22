import unittest
from unittest.mock import patch
from gemini_client import generate_text
from classifier import _build_classification_prompt


class GeminiTests(unittest.TestCase):
    @patch.dict('os.environ', {'GEMINI_API_KEY': 'synthetic-test-key'})
    @patch('gemini_client.requests.post')
    def test_complete_response_and_json_configuration(self, post):
        post.return_value.json.return_value = {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': '{"ok":true}'}]}}]}
        self.assertEqual(generate_text('synthetic', {'ai': {}}, json_mode=True), '{"ok":true}')
        self.assertNotIn('synthetic-test-key', post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs['json']['generationConfig']['responseMimeType'], 'application/json')

    @patch.dict('os.environ', {'GEMINI_API_KEY': 'synthetic-test-key'})
    @patch('gemini_client.requests.post')
    def test_truncated_or_empty_response_is_not_a_valid_reply(self, post):
        for candidate in ({'finishReason': 'MAX_TOKENS'}, {'finishReason': 'STOP', 'content': {'parts': []}}):
            post.return_value.json.return_value = {'candidates': [candidate]}
            with self.assertRaises(RuntimeError): generate_text('synthetic', {'ai': {}})

    def test_classification_receives_body_beyond_first_500_characters(self):
        self.assertIn('Important final request', _build_classification_prompt({'body': 'x'*1500+'Important final request'}))
