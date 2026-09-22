"""
ai_engine.py — Model-agnostic AI reply generator.
Supports OpenRouter, OpenAI GPT, Google Gemini, and Anthropic Claude.
Switch models by changing `ai.model` in config.yaml.
"""

import os
import yaml
from dotenv import load_dotenv

load_dotenv()

PROVIDER_KEY_NAMES = {
    "openrouter": "OPENROUTER_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
}

PROVIDER_LABELS = {
    "openrouter": "OpenRouter",
    "openai": "OpenAI",
    "gemini": "Gemini",
    "claude": "Claude",
}

SYSTEM_PROMPT = """You are a professional email assistant. Your job is to write smart, concise, and contextually appropriate email replies.

Rules:
- Match the sender's tone (formal if they are formal, casual if they are casual)
- Be concise — get to the point quickly, avoid filler phrases
- Never invent facts; reply only using information provided in the email
- If you need clarification on something, politely ask one focused question
- Do NOT start with clichés like "I hope this email finds you well"
- Do NOT include a subject line — only write the reply body
- Do NOT add meta-commentary like "Here is a reply:" — just write the reply
- Sound like a real person, not a corporate robot"""


def load_config() -> dict:
    with open("config.yaml") as f:
        return yaml.safe_load(f)


def generate_reply(email: dict, thread_history: list = None, config: dict = None) -> str:
    """
    Generate an AI-powered email reply.
    
    Args:
        email: Normalized email dict (id, sender, subject, body, date, etc.)
        thread_history: List of previous emails in the thread (optional)
        config: Loaded config.yaml dict (loaded automatically if None)
    
    Returns:
        str: The generated reply body text
    """
    if config is None:
        config = load_config()

    prompt = _build_prompt(email, thread_history, config)
    return generate_from_prompt(prompt, config)


def configured_provider_order(config: dict) -> list[str]:
    """Return the preferred provider followed by configured fallbacks."""
    preferred = (config.get("ai", {}).get("model") or "openai").lower()
    if preferred not in PROVIDER_KEY_NAMES:
        raise ValueError(
            f"Unknown AI model '{preferred}'. "
            "Set ai.model to: openrouter | openai | gemini | claude in config.yaml"
        )
    fallback_order = config.get("ai", {}).get("fallback_order") or ["openrouter", "gemini", "openai", "claude"]
    providers = [preferred]
    for provider in fallback_order:
        provider = str(provider).lower()
        if provider in PROVIDER_KEY_NAMES and provider not in providers:
            providers.append(provider)
    for provider in PROVIDER_KEY_NAMES:
        if provider not in providers:
            providers.append(provider)
    return providers


def available_ai_providers(config: dict) -> list[str]:
    return [
        provider for provider in configured_provider_order(config)
        if os.getenv(PROVIDER_KEY_NAMES[provider])
    ]


def is_quota_error(error: Exception) -> bool:
    text = str(error).lower()
    return any(marker in text for marker in ("credit_balance_exhausted", "insufficient_quota", "quota"))


def generate_from_prompt(prompt: str, config: dict) -> str:
    """Generate text using the configured provider, falling back when needed."""
    errors = []
    for provider in available_ai_providers(config):
        try:
            result = _reply_with_provider(provider, prompt, config)
            config["_ai_provider_used"] = provider
            config["_ai_provider_fallback"] = provider != (config.get("ai", {}).get("model") or "openai").lower()
            return result
        except Exception as error:
            errors.append(f"{PROVIDER_LABELS.get(provider, provider)}: {error}")
            config["_ai_provider_error"] = str(error)
            config["_ai_provider_error_type"] = "quota" if is_quota_error(error) else "provider_error"
            continue
    if not errors:
        raise RuntimeError("No configured AI provider API key is available")
    raise RuntimeError("All configured AI providers failed. " + " | ".join(errors))


def _reply_with_provider(provider: str, prompt: str, config: dict) -> str:
    if provider == "openrouter":
        return _reply_openrouter(prompt, config)
    if provider == "openai":
        return _reply_openai(prompt, config)
    if provider == "gemini":
        return _reply_gemini(prompt, config)
    if provider == "claude":
        return _reply_claude(prompt, config)
    raise ValueError(f"Unknown AI provider: {provider}")


def _build_prompt(email: dict, thread_history: list, config: dict) -> str:
    """Constructs the full LLM prompt from email context and user preferences."""
    thread_section = ""
    if thread_history:
        thread_section = "\n\n--- PREVIOUS MESSAGES IN THREAD (oldest first) ---"
        for past in thread_history[-3:]:  # Max 3 previous messages for context
            thread_section += (
                f"\n\nFrom: {past.get('sender_name', '')} <{past.get('sender', '')}>\n"
                f"{past.get('body', '')[:500]}\n"
                + "─" * 40
            )

    style = config.get("user_style", {})
    avoid = ", ".join(style.get("avoid_phrases", []))
    signature = style.get("signature", "").strip()
    sig_instruction = (f"\nEnd with exactly this signature:\n{signature}" if signature else
        "\nDo not add a closing sign-off, sender name, or signature.")

    # Continuous style learning from past user edits
    learning_section = ""
    try:
        import storage
        memory = storage.get_style_memory()
        recent_edits = memory.get("edits", [])
        if recent_edits:
            learning_section = "\n\n--- CONTINUOUS LEARNING / RECENT USER EDITS ---\n"
            learning_section += "The user previously adjusted your replies to fit their preferred phrasing:\n"
            for ed in recent_edits[-2:]:
                learning_section += f"- User preferred: \"{ed.get('user_edited', '')[:100]}\"\n"
    except Exception:
        pass

    return f"""Write a reply to the following email.

--- EMAIL TO REPLY TO ---
From: {email.get("sender_name", "")} <{email.get("sender", "")}>
Subject: {email.get("subject", "")}
Date: {email.get("date", "")}

{email.get("body", "").strip()}
{thread_section}

--- YOUR WRITING PREFERENCES ---
Tone: {style.get("tone", "professional")}
Additional preferences: {style.get("instructions", "")}
Your name: {style.get("name") or "not configured"}
Avoid these phrases: {avoid or "none specified"}
{sig_instruction}{learning_section}

--- TASK ---
{config.get('_rewrite_instruction', '')}
Current reply to revise (if provided):
{config.get('_current_reply', '')}
Write ONLY the reply body. No subject line. No "Here is a draft:" or similar. Just the reply."""


def record_style_diff(original_ai_reply: str, edited_user_reply: str, context: str = ""):
    """Stores differences between AI suggestions and user-edited replies for continuous style learning."""
    if not original_ai_reply or not edited_user_reply or original_ai_reply.strip() == edited_user_reply.strip():
        return
    try:
        import storage
        from datetime import datetime, timezone
        memory = storage.get_style_memory()
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "original_ai": original_ai_reply.strip()[:300],
            "user_edited": edited_user_reply.strip()[:300],
            "context": context[:100],
        }
        edits = memory.get("edits", [])
        edits.append(entry)
        memory["edits"] = edits[-25:]
        storage.save_style_memory(memory)
    except Exception as e:
        print(f"      ⚠️ Could not save style memory: {e}")



def _reply_openai(prompt: str, config: dict) -> str:
    """Generate reply using OpenAI GPT."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError('OpenAI API key is not configured')
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=config["ai"].get("openai_model", "gpt-4o"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=config["ai"].get("temperature", 0.7),
        max_tokens=config["ai"].get("max_reply_tokens", 600),
    )
    return response.choices[0].message.content.strip()


def _reply_openrouter(prompt: str, config: dict) -> str:
    """Generate a reply through OpenRouter's OpenAI-compatible API."""
    from openrouter_client import generate_text
    return generate_text(prompt, config, system=SYSTEM_PROMPT)


def _reply_gemini(prompt: str, config: dict) -> str:
    """Generate reply using Google Gemini."""
    from gemini_client import generate_text
    return generate_text(prompt, config, system=SYSTEM_PROMPT)


def _reply_claude(prompt: str, config: dict) -> str:
    """Generate reply using Anthropic Claude."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError('Anthropic API key is not configured')
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=config["ai"].get("claude_model", "claude-3-5-sonnet-20241022"),
        max_tokens=config["ai"].get("max_reply_tokens", 600),
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def _demo_fallback_reply(prompt: str) -> str:
    """Provides a contextual demo reply when API keys are not yet configured."""
    if "Budget & Roadmap" in prompt:
        return (
            "Hi Sarah,\n\n"
            "Thursday at 2 PM EST works great for me. I'll review the Q3 budget allocation beforehand "
            "and bring the updated product roadmap slides to our meeting.\n\n"
            "Looking forward to connecting!"
        )
    elif "URGENT: API Authentication Issue" in prompt:
        return (
            "Hi David,\n\n"
            "Thanks for flagging this. I'm looking into the 401 Unauthorized errors on the payment gateway right now. "
            "Our team is investigating the token refresh lifecycle and will update you within the next 30 minutes."
        )
    elif "Design Mockups" in prompt:
        return (
            "Hi Alex,\n\n"
            "Thanks for sharing the updated Figma prototypes! The dark mode interface looks fantastic. "
            "I'll review the flows in detail and share my feedback ahead of Friday's deadline."
        )
    else:
        return (
            "Hi,\n\n"
            "Thank you for reaching out. I have received your message and will review the details shortly."
        )
