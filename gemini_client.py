"""Gemini text REST adapter using the documented generateContent endpoint.

Reference: https://ai.google.dev/api/generate-content
"""
import os
import time
import requests


def generate_text(prompt, config, system=None, json_mode=False):
    key = os.getenv('GEMINI_API_KEY')
    if not key:
        raise RuntimeError('Gemini API key is not configured')
    settings = config.get('ai', {})
    model = settings.get('gemini_model', 'gemini-3.6-flash')
    if not isinstance(model, str) or not all(char.isalnum() or char in '.-_' for char in model):
        raise ValueError('Invalid Gemini model name')
    generation = {'temperature': 0 if json_mode else settings.get('temperature', .7),
        'maxOutputTokens': 2048 if json_mode else settings.get('max_reply_tokens', 2048)}
    if model.startswith('gemini-2.5-flash'):
        generation['thinkingConfig'] = {'thinkingBudget': 0}
    if json_mode:
        generation['responseMimeType'] = 'application/json'
    payload = {'contents':[{'role':'user','parts':[{'text':prompt}]}], 'generationConfig':generation}
    if system:
        payload['systemInstruction'] = {'parts':[{'text':system}]}
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
    response = None
    for attempt in range(3):
        response = requests.post(url, headers={'x-goog-api-key':key,'Content-Type':'application/json'},
            json=payload, timeout=60)
        if response.status_code not in (429, 500, 502, 503, 504) or attempt == 2:
            break
        time.sleep(1.5 * (attempt + 1))
    response.raise_for_status()
    candidates = response.json().get('candidates', [])
    if not candidates or candidates[0].get('finishReason') != 'STOP':
        raise RuntimeError('Gemini did not return a complete response; retry or increase the response token limit')
    text = ''.join(part.get('text','') for part in candidates[0].get('content',{}).get('parts',[]) if not part.get('thought')).strip()
    if not text:
        raise RuntimeError('Gemini returned no text')
    return text
