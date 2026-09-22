import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import openrouter_client


class OpenRouterClientTests(unittest.TestCase):
    @patch("openai.OpenAI")
    def test_text_request_uses_configured_model_and_endpoint(self, openai):
        client = MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Reply text"))]
        )
        openai.return_value = client
        config = {"ai": {"openrouter_model": "anthropic/claude-sonnet-4", "max_reply_tokens": 500}}
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test"}, clear=True):
            result = openrouter_client.generate_text("Hello", config, system="Be concise")
        self.assertEqual(result, "Reply text")
        openai.assert_called_once()
        self.assertEqual(openai.call_args.kwargs["base_url"], "https://openrouter.ai/api/v1")
        self.assertEqual(client.chat.completions.create.call_args.kwargs["model"], "anthropic/claude-sonnet-4")

    @patch("openai.OpenAI")
    def test_json_request_enables_json_object_response(self, openai):
        client = MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))]
        )
        openai.return_value = client
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test"}, clear=True):
            result = openrouter_client.generate_text("Classify", {"ai": {}}, json_mode=True)
        self.assertEqual(result, '{"ok": true}')
        request = client.chat.completions.create.call_args.kwargs
        self.assertEqual(request["response_format"], {"type": "json_object"})
        self.assertEqual(request["temperature"], 0)


if __name__ == "__main__":
    unittest.main()
