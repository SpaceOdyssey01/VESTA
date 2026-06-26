"""JSONL loading helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

from .schemas import AttackTool, NormalTool, TaskSpec


def read_jsonl(path: str | Path) -> Iterable[dict]:
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_tasks(path: str | Path) -> List[TaskSpec]:
    tasks: List[TaskSpec] = []
    for idx, item in enumerate(read_jsonl(path), 1):
        if "tasks" in item:
            for task_idx, task_text in enumerate(item["tasks"], 1):
                tasks.append(
                    TaskSpec(
                        task_id=f"{item.get('agent_name', 'agent')}_{task_idx:04d}",
                        agent_name=item.get("agent_name", ""),
                        task=task_text,
                        expected_tools=item.get("expected_tools", []),
                        metadata={"source_row": idx, **item.get("metadata", {})},
                    )
                )
        else:
            tasks.append(
                TaskSpec(
                    task_id=item.get("task_id", f"task_{idx:04d}"),
                    agent_name=item.get("agent_name", item.get("agent_role", "")),
                    task=item["task"],
                    expected_tools=item.get("expected_tools", []),
                    metadata=item.get("metadata", {}),
                )
            )
    return tasks


def load_normal_tools(path: str | Path) -> List[NormalTool]:
    tools: List[NormalTool] = []
    for item in read_jsonl(path):
        tools.append(
            NormalTool(
                name=item.get("Tool Name", item.get("name")),
                description=item.get("Description", item.get("description", "")),
                expected_achievement=item.get(
                    "Expected Achievements",
                    item.get("expected_achievement", ""),
                ),
                target_agent=item.get("Corresponding Agent", item.get("target_agent", "")),
            )
        )
    return tools


def load_attack_tools(path: str | Path) -> List[AttackTool]:
    tools: List[AttackTool] = []
    for item in read_jsonl(path):
        aggressive = item.get("Aggressive", item.get("aggressive", False))
        if isinstance(aggressive, str):
            aggressive = aggressive.lower() == "true"
        tools.append(
            AttackTool(
                name=item.get("Attacker Tool", item.get("name")),
                instruction=item.get("Attacker Instruction", item.get("instruction", "")),
                description=item.get("Description", item.get("description", "")),
                attack_goal=item.get("Attack goal", item.get("attack_goal", "")),
                target_agent=item.get("Corresponding Agent", item.get("target_agent", "")),
                aggressive=aggressive,
                attack_type_label=item.get("Attack Type", item.get("attack_type_label", "")),
            )
        )
    return tools
