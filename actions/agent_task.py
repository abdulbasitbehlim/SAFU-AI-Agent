"""Plan and execute safe multi-step desktop workflows using SAFU's action registry."""
from __future__ import annotations

import json
import re
from pathlib import Path

from core.action_loader import discover_actions
from core.model_router import generate

_BASE = Path(__file__).resolve().parent.parent


def _extract_json(text: str):
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.I)
    t = re.sub(r"\s*```$", "", t)
    first = min([i for i in (t.find("["), t.find("{")) if i >= 0], default=0)
    t = t[first:]
    return json.loads(t)


def agent_task(parameters=None, response=None, player=None, session_memory=None, speak=None) -> str:
    p = parameters or {}
    task = (p.get("task") or "").strip()
    if not task:
        return "No automation task provided."
    max_steps = max(1, min(int(p.get("max_steps", 10) or 10), 15))

    registry = discover_actions(
        _BASE / "actions",
        reserved_names={"agent_task"},
        logger=lambda _m: None,
    )
    blocked = {"agent_task", "model_delegate"}
    decls = [d for d in registry.get_tool_declarations() if d["name"] not in blocked]
    compact = [{"name": d["name"], "description": d["description"], "parameters": d["parameters"]} for d in decls]

    planner_prompt = f"""You are SAFU's automation planner. Convert the user's request into a short sequence of executable tool calls.

USER REQUEST:
{task}

AVAILABLE TOOLS:
{json.dumps(compact, ensure_ascii=False)}

Return ONLY a JSON array. Each element must be exactly:
{{"tool":"tool_name","args":{{...}},"why":"short reason"}}

Rules:
- Maximum {max_steps} steps.
- Use document_creator or file_controller whenever the user asks to create/save a file. Never merely describe the file.
- For a Desktop request, use location/path "desktop" so Windows folder redirection is handled correctly.
- Do not invent tools or parameters.
- Keep steps minimal and ordered.
- Never include agent_task or model_delegate in the plan.
"""
    try:
        plan_text, provider, model = generate(planner_prompt, provider=(p.get("provider") or "auto"))
        plan = _extract_json(plan_text)
    except Exception as e:
        return f"Could not plan the automation task: {e}"

    if not isinstance(plan, list):
        return "Automation planner returned an invalid plan."
    plan = plan[:max_steps]
    results = []
    ctx = {"player": player, "speak": speak, "response": response, "session_memory": session_memory}

    for idx, step in enumerate(plan, 1):
        if not isinstance(step, dict):
            results.append(f"Step {idx}: skipped invalid plan item")
            continue
        name = str(step.get("tool", "")).strip()
        args = step.get("args") if isinstance(step.get("args"), dict) else {}
        if name in blocked or not registry.has(name):
            results.append(f"Step {idx}: unavailable tool '{name}'")
            continue
        if player:
            player.write_log(f"[agent] {idx}/{len(plan)} {name}")
        result = registry.run(name, args, ctx)
        results.append(f"Step {idx} — {name}: {result}")
        # Stop on clear failure so later steps do not compound it.
        low = str(result).lower()
        if any(marker in low for marker in (" failed:", "could not ", "access denied", "unknown action", "not available")):
            break

    return (
        f"Automation plan executed with {provider}:{model}.\n" + "\n".join(results)
    )


TOOL = {
    "name": "agent_task",
    "description": (
        "Plans and executes a multi-step computer workflow (2+ dependent steps) using Safu's real actions. "
        "Use for requests such as create files then open them, organize folders then launch an app, research then save results, or other chained automation."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "task": {"type": "STRING", "description": "The complete user goal, including filenames/locations/details"},
            "provider": {"type": "STRING", "description": "auto | gemini | openai | anthropic | ollama | openai_compatible"},
            "max_steps": {"type": "INTEGER", "description": "Maximum workflow steps, 1-15"},
        },
        "required": ["task"],
    },
    "handler": agent_task,
}
