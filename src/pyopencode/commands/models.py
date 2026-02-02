from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass
class CommandSpec:
    name: str
    description: str = ""
    agent: str | None = None
    prompt: str = ""
    source_path: Path | None = None
    model: str | None = None
    max_steps: int | None = None

    @staticmethod
    def from_obj(name: str, obj: Any) -> "CommandSpec | None":
        if not isinstance(obj, dict):
            return None
        desc = obj.get("description", "")
        agent = obj.get("agent")
        prompt = obj.get("prompt", "")
        model = obj.get("model")
        max_steps = obj.get("max_steps")
        if not isinstance(desc, str):
            desc = ""
        if agent is not None and not isinstance(agent, str):
            agent = None
        if not isinstance(prompt, str):
            return None
        if model is not None and not isinstance(model, str):
            model = None
        if max_steps is not None and not isinstance(max_steps, int):
            max_steps = None
        return CommandSpec(
            name=name,
            description=desc,
            agent=agent,
            prompt=prompt,
            model=model,
            max_steps=max_steps,
        )
