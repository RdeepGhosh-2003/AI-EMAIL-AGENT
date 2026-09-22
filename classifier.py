"""
classifier.py — LLM-based email classifier.
Classifies each email for priority, category, sentiment, and reply intent
before passing to the AI reply generator.
"""

import json
import os
from dotenv import load_dotenv

load_dotenv()

CLASSIFICATION_SCHEMA = """{
  "priority": "high" | "medium" | "low",
  "category": "question" | "meeting_request" | "follow_up" | "complaint" | "information" | "newsletter" | "spam" | "promotional" | "other",
  "needs_reply": true | false,
  "sentiment": "positive" | "neutral" | "negative" | "urgent",
  "auto_reply_safe": true | false,
  "confidence": 0.0 to 1.0,
  "summary": "One sentence summary of the email's main point"
}"""


def is_vip_contact(sender: str, config: dict) -> bool:
    vip_contacts = config.get("agent", {}).get("vip_contacts") or []
    if isinstance(vip_contacts, str):
        vip_contacts = [v.strip() for v in vip_contacts.split(",") if v.strip()]
    sender_lower = (sender or "").lower()
    for vip in vip_contacts:
        v = vip.strip().lower()
        if not v:
            continue
        if v.startswith("*@"):
            domain = v[2:]
            if sender_lower.endswith("@" + domain) or sender_lower.endswith("." + domain):
                return True
        elif v in sender_lower:
            return True
    return False


def classify_email(email: dict, config: dict) -> dict:
    """
    Classify an email using the configured AI model.
    
    Returns a dict with: priority, category, needs_reply,
    sentiment, auto_reply_safe, summary, is_vip
    """
    prompt = _build_classification_prompt(email)
    try:
        from ai_engine import available_ai_providers, PROVIDER_LABELS, is_quota_error
        errors = []
        result = None
        preferred = (config.get("ai", {}).get("model") or "openai").lower()
        for provider in available_ai_providers(config):
            try:
                result = _classify_with_provider(provider, prompt, config)
                config["_ai_provider_used"] = provider
                config["_ai_provider_fallback"] = provider != preferred
                break
            except Exception as error:
                errors.append(f"{PROVIDER_LABELS.get(provider, provider)}: {error}")
                config["_ai_provider_error"] = str(error)
                config["_ai_provider_error_type"] = "quota" if is_quota_error(error) else "provider_error"
        if result is None:
            raise RuntimeError("All configured AI providers failed. " + " | ".join(errors))

        # Validate required keys exist
        required = ["priority", "category", "needs_reply", "sentiment"]
        for key in required:
            if key not in result:
                result[key] = _default_classification()[key]

        # Check VIP allowlist
        if is_vip_contact(email.get("sender", ""), config):
            result["is_vip"] = True
            result["priority"] = "high"

        return result

    except Exception as e:
        print(f"      ⚠️  Classification error: {e} — using defaults")
        def_res = _default_classification()
        if is_vip_contact(email.get("sender", ""), config):
            def_res["is_vip"] = True
            def_res["priority"] = "high"
        return def_res


def _build_classification_prompt(email: dict) -> str:
    return f"""Classify this email. Return ONLY valid JSON — no markdown, no explanation.

Subject: {email.get("subject", "")}
From: {email.get("sender", "")}
Body: {email.get("body", "")}

Return exactly this JSON structure:
{CLASSIFICATION_SCHEMA}

Guidance:
- needs_reply: false for newsletters, automated notifications, receipts, spam
- auto_reply_safe: true only for simple, clear questions or confirmations
- priority high: urgent requests, complaints, emails from important contacts
- Return ONLY the JSON object"""


def _classify_openai(prompt: str, config: dict) -> dict:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=config["ai"].get("openai_model", "gpt-4o-mini"),
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(response.choices[0].message.content)


def _classify_with_provider(provider: str, prompt: str, config: dict) -> dict:
    if provider == "openrouter":
        return _classify_openrouter(prompt, config)
    if provider == "openai":
        return _classify_openai(prompt, config)
    if provider == "gemini":
        return _classify_gemini(prompt, config)
    if provider == "claude":
        return _classify_claude(prompt, config)
    return _default_classification()


def _classify_openrouter(prompt: str, config: dict) -> dict:
    from openrouter_client import generate_text
    return json.loads(generate_text(prompt, config, json_mode=True))


def _classify_gemini(prompt: str, config: dict) -> dict:
    from gemini_client import generate_text
    return json.loads(generate_text(prompt, config, json_mode=True))


def _classify_claude(prompt: str, config: dict) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    message = client.messages.create(
        model=config["ai"].get("claude_model", "claude-3-5-sonnet-20241022"),
        max_tokens=250,
        messages=[{"role": "user", "content": prompt}],
    )
    text = message.content[0].text.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def _default_classification() -> dict:
    return {
        "priority": "medium",
        "category": "other",
        "needs_reply": True,
        "sentiment": "neutral",
        "auto_reply_safe": False,
        "confidence": 0.0,
        "classification_failed": True,
        "summary": "Could not classify — review manually",
    }
