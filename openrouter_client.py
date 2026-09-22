"""OpenRouter adapter using its OpenAI-compatible chat-completions API."""

import os


def generate_text(prompt, config, system=None, json_mode=False):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OpenRouter API key is not configured")

    settings = config.get("ai", {})
    model = settings.get("openrouter_model", "google/gemini-2.5-flash")
    if not isinstance(model, str) or "/" not in model or not all(
        char.isalnum() or char in ".-_:~/" for char in model
    ):
        raise ValueError("Invalid OpenRouter model slug")

    from openai import OpenAI

    headers = {"X-OpenRouter-Title": "AI Email Agent"}
    app_url = os.getenv("OPENROUTER_APP_URL", "").strip()
    if app_url:
        headers["HTTP-Referer"] = app_url
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers=headers,
        timeout=60.0,
        max_retries=2,
    )
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    request = {
        "model": model,
        "messages": messages,
        "temperature": 0 if json_mode else settings.get("temperature", 0.7),
        "max_tokens": 2048 if json_mode else settings.get("max_reply_tokens", 2048),
    }
    if json_mode:
        request["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**request)
    text = response.choices[0].message.content
    if not text or not text.strip():
        raise RuntimeError("OpenRouter returned no text")
    return text.strip()
