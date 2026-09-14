"""Text-model router for SAFU.

Gemini Live remains the low-latency voice/orchestration channel. This module lets
SAFU delegate a heavy text task to Gemini text, OpenAI, Anthropic, Ollama, or an
OpenAI-compatible local server (LM Studio / llama.cpp / Jan / LocalAI).
"""
from __future__ import annotations

import json
from typing import Iterable

import requests

from memory.config_manager import (
    get_anthropic_key, get_brain_settings, get_gemini_key, get_openai_key,
)


def _provider_order(preferred: str) -> list[str]:
    p = (preferred or "auto").lower().strip()
    if p != "auto":
        return [p]
    # Fast/local first when it is already running, then configured cloud brains.
    return ["ollama", "openai_compatible", "openai", "anthropic", "gemini"]


def _extract_openai_response(data: dict) -> str:
    text = data.get("output_text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    chunks: list[str] = []
    for item in data.get("output", []) or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for part in item.get("content", []) or []:
            if isinstance(part, dict) and part.get("type") in {"output_text", "text"}:
                t = part.get("text")
                if isinstance(t, str) and t.strip():
                    chunks.append(t.strip())
    return "\n".join(chunks).strip()


def _gemini(prompt: str, model: str) -> str:
    key = get_gemini_key()
    if not key:
        raise RuntimeError("Gemini API key is not configured")
    from google import genai
    client = genai.Client(api_key=key)
    r = client.models.generate_content(model=model, contents=prompt)
    return (r.text or "").strip()


def _openai(prompt: str, model: str, timeout: int) -> str:
    key = get_openai_key()
    if not key:
        raise RuntimeError("OpenAI API key is not configured")
    r = requests.post(
        "https://api.openai.com/v1/responses",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "instructions": "You are a specialist sub-agent inside SAFU. Return only the useful result in English.",
            "input": prompt,
            "max_output_tokens": 4000,
        },
        timeout=timeout,
    )
    r.raise_for_status()
    out = _extract_openai_response(r.json())
    if not out:
        raise RuntimeError("OpenAI returned no text")
    return out


def _anthropic(prompt: str, model: str, timeout: int) -> str:
    key = get_anthropic_key()
    if not key:
        raise RuntimeError("Anthropic API key is not configured")
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 4000,
            "system": "You are a specialist sub-agent inside SAFU. Return only the useful result in English.",
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=timeout,
    )
    r.raise_for_status()
    chunks = []
    for block in r.json().get("content", []) or []:
        if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
            chunks.append(block["text"])
    out = "\n".join(chunks).strip()
    if not out:
        raise RuntimeError("Anthropic returned no text")
    return out


def _ollama(prompt: str, url: str, model: str, timeout: int) -> str:
    r = requests.post(
        f"{url.rstrip('/')}/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a specialist sub-agent inside SAFU. Reply in English."},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "keep_alive": -1,
            "options": {"num_predict": 4000},
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return ((r.json().get("message") or {}).get("content") or "").strip()


def _openai_compatible(prompt: str, url: str, model: str, timeout: int) -> str:
    r = requests.post(
        f"{url.rstrip('/')}/v1/chat/completions",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a specialist sub-agent inside SAFU. Reply in English."},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "max_tokens": 4000,
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return (((r.json().get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()


def generate(task: str, provider: str = "auto", model: str = "", timeout: int = 180) -> tuple[str, str, str]:
    """Return (text, provider_used, model_used), trying fallbacks in auto mode."""
    cfg = get_brain_settings()
    preferred = (provider or cfg["provider"] or "auto").lower().strip()
    errors: list[str] = []

    for p in _provider_order(preferred):
        try:
            if p == "gemini":
                m = model or cfg["gemini_model"]
                text = _gemini(task, m)
            elif p == "openai":
                m = model or cfg["openai_model"]
                text = _openai(task, m, timeout)
            elif p == "anthropic":
                m = model or cfg["anthropic_model"]
                text = _anthropic(task, m, timeout)
            elif p in {"ollama", "local"}:
                m = model or cfg["local_model"]
                text = _ollama(task, cfg["local_url"], m, timeout)
                p = "ollama"
            elif p in {"openai_compatible", "lmstudio", "llamacpp", "jan", "localai"}:
                m = model or cfg["local_model"]
                text = _openai_compatible(task, cfg["local_url"], m, timeout)
                p = "openai_compatible"
            else:
                errors.append(f"unknown provider {p}")
                continue
            if text:
                return text, p, m
            errors.append(f"{p}: empty response")
        except Exception as e:
            errors.append(f"{p}: {e}")
            if preferred != "auto":
                break

    raise RuntimeError("No model completed the task. " + " | ".join(errors[:5]))


def status() -> dict:
    cfg = get_brain_settings()
    result = {
        "preferred": cfg["provider"],
        "gemini": bool(get_gemini_key()),
        "openai": bool(get_openai_key()),
        "anthropic": bool(get_anthropic_key()),
        "local_url": cfg["local_url"],
        "local_model": cfg["local_model"],
        "ollama_reachable": False,
        "openai_compatible_reachable": False,
    }
    try:
        result["ollama_reachable"] = requests.get(f"{cfg['local_url']}/api/tags", timeout=1.2).ok
    except Exception:
        pass
    try:
        result["openai_compatible_reachable"] = requests.get(f"{cfg['local_url']}/v1/models", timeout=1.2).ok
    except Exception:
        pass
    return result
