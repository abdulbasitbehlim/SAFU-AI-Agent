"""Delegate difficult text work to an alternate configured model."""
from core.model_router import generate, status


def model_delegate(parameters=None, response=None, player=None, session_memory=None) -> str:
    p = parameters or {}
    action = (p.get("action") or "run").strip().lower()
    if action == "status":
        s = status()
        return (
            f"Preferred={s['preferred']}; Gemini={'yes' if s['gemini'] else 'no'}; "
            f"OpenAI={'yes' if s['openai'] else 'no'}; Anthropic={'yes' if s['anthropic'] else 'no'}; "
            f"local model={s['local_model']} at {s['local_url']}; "
            f"Ollama reachable={s['ollama_reachable']}; OpenAI-compatible reachable={s['openai_compatible_reachable']}."
        )
    task = (p.get("task") or "").strip()
    if not task:
        return "No task was provided for model delegation."
    provider = (p.get("provider") or "auto").strip().lower()
    model = (p.get("model") or "").strip()
    if player:
        player.write_log(f"[brain] delegating to {provider}{' / ' + model if model else ''}")
    text, used, used_model = generate(task, provider=provider, model=model)
    return f"[MODEL={used}:{used_model}]\n{text}"


TOOL = {
    "name": "model_delegate",
    "description": (
        "Delegates a difficult reasoning, coding, drafting, summarization, or analysis task to another configured AI model. "
        "Use when the user explicitly asks for OpenAI/GPT, Claude/Anthropic, Gemini, Ollama/local, LM Studio, or asks for a second-model check. "
        "Normal quick conversation should NOT use this tool."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "run | status"},
            "task": {"type": "STRING", "description": "Complete task/prompt for the specialist model"},
            "provider": {"type": "STRING", "description": "auto | gemini | openai | anthropic | ollama | openai_compatible"},
            "model": {"type": "STRING", "description": "Optional exact model ID/name; blank uses configured default"},
        },
    },
    "handler": model_delegate,
}
