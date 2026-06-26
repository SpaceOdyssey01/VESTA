"""Benchmark case generation and execution."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Iterable, List, Sequence

from .adapters import AgentAdapter
from .evaluator import evaluate_case
from .injectors import INJECTORS
from .io import load_attack_tools, load_normal_tools, load_tasks
from .schemas import (
    ATTACK_CHANNELS,
    ATTACK_TYPES,
    AttackTool,
    BenchmarkCase,
    BenchmarkResult,
    NormalTool,
    TaskSpec,
)


class BenchmarkRunner:
    def __init__(
        self,
        *,
        tasks: Sequence[TaskSpec],
        normal_tools: Sequence[NormalTool],
        attack_tools: Sequence[AttackTool],
    ):
        self.tasks = list(tasks)
        self.normal_tools = list(normal_tools)
        self.attack_tools = list(attack_tools)

    @classmethod
    def from_jsonl(
        cls,
        *,
        tasks_path: str | Path,
        normal_tools_path: str | Path,
        attack_tools_path: str | Path,
    ) -> "BenchmarkRunner":
        return cls(
            tasks=load_tasks(tasks_path),
            normal_tools=load_normal_tools(normal_tools_path),
            attack_tools=load_attack_tools(attack_tools_path),
        )

    def build_cases(
        self,
        *,
        attack_channels: Iterable[str] = ATTACK_CHANNELS,
        attack_types: Iterable[str] = ATTACK_TYPES,
        trigger: str = "with perspicacious discernment",
    ) -> List[BenchmarkCase]:
        cases: List[BenchmarkCase] = []
        channels = list(attack_channels)
        types = list(attack_types)
        for task in self.tasks:
            task_attack_tools = [
                tool for tool in self.attack_tools if tool.target_agent == task.agent_name
            ]
            if not task_attack_tools:
                task_attack_tools = list(self.attack_tools)

            task_normal_tools = self._normal_tools_for_task(task)
            for attack_tool in task_attack_tools:
                for channel in channels:
                    injector = INJECTORS[channel]
                    for attack_type in types:
                        case_id = (
                            f"{task.task_id}__{attack_tool.name}__{channel}__{attack_type}"
                        )
                        cases.append(
                            injector.build_case(
                                case_id=case_id,
                                task=task,
                                normal_tools=task_normal_tools,
                                attack_tool=attack_tool,
                                attack_type=attack_type,
                                trigger=trigger,
                            )
                        )
        return cases

    def run(
        self,
        *,
        adapter: AgentAdapter,
        attack_channels: Iterable[str] = ATTACK_CHANNELS,
        attack_types: Iterable[str] = ATTACK_TYPES,
        trigger: str = "with perspicacious discernment",
    ) -> List[BenchmarkResult]:
        results: List[BenchmarkResult] = []
        for case in self.build_cases(
            attack_channels=attack_channels,
            attack_types=attack_types,
            trigger=trigger,
        ):
            run = adapter.run(case)
            results.append(
                evaluate_case(
                    case=case,
                    run=run,
                    normal_tools=self._normal_tools_for_task(case.task),
                )
            )
        return results

    def _normal_tools_for_task(self, task: TaskSpec) -> List[NormalTool]:
        selected = [tool for tool in self.normal_tools if tool.name in task.expected_tools]
        if selected:
            return selected

        agent_scoped = [
            tool for tool in self.normal_tools if tool.target_agent == task.agent_name
        ]
        if agent_scoped:
            return agent_scoped

        return list(self.normal_tools)


def summarize_results(results: Sequence[BenchmarkResult]) -> dict:
    total = len(results)
    if total == 0:
        return {"total": 0}
    return {
        "total": total,
        "attack_success_rate": sum(r.attack_success for r in results) / total,
        "task_success_rate": sum(r.task_success for r in results) / total,
        "refusal_rate": sum(r.refusal for r in results) / total,
    }


def result_to_dict(result: BenchmarkResult) -> dict:
    return {
        "case": asdict(result.case),
        "run": asdict(result.run),
        "attack_success": result.attack_success,
        "task_success": result.task_success,
        "refusal": result.refusal,
        "notes": result.notes,
    }
