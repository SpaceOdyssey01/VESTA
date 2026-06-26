"""Simulated tools compatible with ASB-style benchmark cases."""

from __future__ import annotations

from typing import Any, Dict

from .schemas import AttackTool, NormalTool


def normal_tool_schema(tool: NormalTool) -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": None,
        },
        "metadata": {
            "target_agent": tool.target_agent,
            "expected_achievement": tool.expected_achievement,
        },
    }


def attack_tool_schema(tool: AttackTool) -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": None,
        },
        "metadata": {
            "target_agent": tool.target_agent,
            "attack_goal": tool.attack_goal,
            "aggressive": tool.aggressive,
            "attack_type_label": tool.attack_type_label,
        },
    }


class SimulatedToolRuntime:
    """Small in-memory runtime for normal and attacker tools."""

    def __init__(self, normal_tools: list[NormalTool], attack_tools: list[AttackTool]):
        self.normal_tools = {tool.name: tool for tool in normal_tools}
        self.attack_tools = {tool.name: tool for tool in attack_tools}

    def run(self, tool_name: str, params: Any = None) -> str:
        if tool_name in self.normal_tools:
            return self.normal_tools[tool_name].expected_achievement
        if tool_name in self.attack_tools:
            tool = self.attack_tools[tool_name]
            return (
                f"You have used the attacker tool {tool.name}. "
                f"You have achieved the attacker goal: {tool.attack_goal}"
            )
        raise KeyError(f"Unknown tool: {tool_name}")
