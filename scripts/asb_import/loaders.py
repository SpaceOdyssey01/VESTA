"""Load the compact and upstream-style ASB JSONL source formats."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

from .models import AttackTool, NormalTool, TaskSpec


def read_jsonl(path: str | Path) -> Iterable[dict]:
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc.msg}") from exc


def load_tasks(path: str | Path) -> List[TaskSpec]:
    tasks: List[TaskSpec] = []
    for row_number, item in enumerate(read_jsonl(path), 1):
        if "tasks" in item:
            for task_number, task_text in enumerate(item["tasks"], 1):
                tasks.append(
                    TaskSpec(
                        task_id=f"{item.get('agent_name', 'agent')}_{task_number:04d}",
                        agent_name=item.get("agent_name", ""),
                        task=task_text,
                        expected_tools=item.get("expected_tools", []),
                        metadata={"source_row": row_number, **item.get("metadata", {})},
                    )
                )
        else:
            tasks.append(
                TaskSpec(
                    task_id=item.get("task_id", f"task_{row_number:04d}"),
                    agent_name=item.get("agent_name", item.get("agent_role", "")),
                    task=item["task"],
                    expected_tools=item.get("expected_tools", []),
                    metadata=item.get("metadata", {}),
                )
            )
    return tasks


def load_normal_tools(path: str | Path) -> List[NormalTool]:
    return [
        NormalTool(
            name=item.get("Tool Name", item.get("name")),
            description=item.get("Description", item.get("description", "")),
            expected_achievement=item.get(
                "Expected Achievements", item.get("expected_achievement", "")
            ),
            target_agent=item.get("Corresponding Agent", item.get("target_agent", "")),
        )
        for item in read_jsonl(path)
    ]


def load_attack_tools(path: str | Path) -> List[AttackTool]:
    tools: List[AttackTool] = []
    for item in read_jsonl(path):
        aggressive = item.get("Aggressive", item.get("aggressive", False))
        if isinstance(aggressive, str):
            aggressive = aggressive.lower() == "true"
        tools.append(
            AttackTool(
                name=item.get("Attacker Tool", item.get("name")),
                instruction=item.get(
                    "Attacker Instruction", item.get("instruction", "")
                ),
                description=item.get("Description", item.get("description", "")),
                attack_goal=item.get("Attack goal", item.get("attack_goal", "")),
                target_agent=item.get(
                    "Corresponding Agent", item.get("target_agent", "")
                ),
                aggressive=bool(aggressive),
                attack_type_label=item.get(
                    "Attack Type", item.get("attack_type_label", "")
                ),
            )
        )
    return tools
