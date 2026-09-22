import os
import unittest
from unittest.mock import patch

import ai_engine


class AIFallbackTests(unittest.TestCase):
    def test_openrouter_is_available_and_selected_with_its_key(self):
        config = {"ai": {"model": "openrouter"}}
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "openrouter-key"}, clear=True):
            self.assertEqual(ai_engine.available_ai_providers(config), ["openrouter"])

    def test_openai_failure_falls_back_to_gemini_for_same_prompt(self):
        config = {"ai": {"model": "openai", "fallback_order": ["gemini"]}}
        with patch.dict(os.environ, {"OPENAI_API_KEY": "openai-key", "GEMINI_API_KEY": "gemini-key"}, clear=False):
            with patch.object(ai_engine, "_reply_openai", side_effect=RuntimeError("credit_balance_exhausted")) as openai:
                with patch.object(ai_engine, "_reply_gemini", return_value="Gemini reply") as gemini:
                    result = ai_engine.generate_from_prompt("Reply to this email", config)

        self.assertEqual(result, "Gemini reply")
        self.assertEqual(config["_ai_provider_used"], "gemini")
        self.assertTrue(config["_ai_provider_fallback"])
        self.assertEqual(config["_ai_provider_error_type"], "quota")
        openai.assert_called_once()
        gemini.assert_called_once()


if __name__ == "__main__":
    unittest.main()
