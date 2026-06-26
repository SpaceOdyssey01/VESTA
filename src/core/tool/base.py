from abc import ABC, abstractmethod
from typing import Dict

from src.core.tool.schema import ToolExecutionInput, ToolExecutionResult, ToolSpec


class BaseTool(ABC):
    def __init__(self, spec: ToolSpec):
        self.spec = spec

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def description(self) -> str:
        return self.spec.description

    @abstractmethod
    def execute(self, execution_input: ToolExecutionInput) -> ToolExecutionResult:
        pass

    def get_spec(self) -> ToolSpec:
        return self.spec


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, tool_name: str) -> BaseTool:
        if tool_name not in self._tools:
            raise ValueError(f"未找到工具: {tool_name}")
        return self._tools[tool_name]

    def has(self, tool_name: str) -> bool:
        return tool_name in self._tools

    def list_specs(self):
        return [tool.get_spec() for tool in self._tools.values()]