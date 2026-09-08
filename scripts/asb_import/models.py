"""Minimal ASB source models needed by the offline importer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


ATTACK_CHANNELS = ("dpi", "opi", "mp", "pot")
ATTACK_TYPES = (
    "naive",
    "fake_completion",
    "escape_characters",
    "context_ignoring",
    "combined_attack",
)


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    agent_name: str
    task: str
    expected_tools: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalTool:
    name: str
    description: str
    expected_achievement: str
    target_agent: str = ""


@dataclass(frozen=True)
class AttackTool:
    name: str
    instruction: str
    description: str
    attack_goal: str
    target_agent: str
    aggressive: bool = False
    attack_type_label: str = "Stealthy Attack"


@dataclass
class BenchmarkCase:
    case_id: str
    task: TaskSpec
    attack_tool: AttackTool
    attack_channel: str
    attack_type: str
    injected_task: str
    tools: List[Dict[str, Any]]
    observation_suffix: Optional[str] = None
    memory_context: Optional[str] = None
    planner_context: Optional[str] = None
    trigger: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
