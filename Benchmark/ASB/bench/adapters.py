"""Agent adapters.

Real projects should implement `AgentAdapter.run`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List

from .schemas import AgentRunResult, BenchmarkCase


class AgentAdapter(ABC):
    @abstractmethod
    def run(self, case: BenchmarkCase) -> AgentRunResult:
        raise NotImplementedError


class MockAgentAdapter(AgentAdapter):
    """A deterministic adapter for smoke-testing the benchmark harness.

    It is intentionally simple: if the injected task or auxiliary contexts contain
    the attacker tool name, it records an attacker-tool call. Otherwise, it records
    calls to the task's expected tools.
    """

    def run(self, case: BenchmarkCase) -> AgentRunResult:
        contexts = "\n".join(
            item
            for item in [
                case.injected_task,
                case.observation_suffix,
                case.memory_context,
                case.planner_context,
            ]
            if item
        )

        tool_calls: List[Dict] = []
        messages = [{"role": "user", "content": case.injected_task}]

        if case.attack_tool.name in contexts:
            tool_calls.append(
                {
                    "tool_name": case.attack_tool.name,
                    "arguments": {},
                    "response": case.attack_tool.attack_goal,
                }
            )
            final_output = (
                f"Used attacker tool {case.attack_tool.name}. "
                f"{case.attack_tool.attack_goal}"
            )
        else:
            for tool_name in case.task.expected_tools:
                tool_calls.append({"tool_name": tool_name, "arguments": {}, "response": ""})
            final_output = "Task completed."

        messages.append({"role": "assistant", "content": final_output})
        return AgentRunResult(
            case_id=case.case_id,
            final_output=final_output,
            messages=messages,
            tool_calls=tool_calls,
        )

