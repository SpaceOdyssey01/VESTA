#负责把tool names变成真正可执行的模拟工具实例
from typing import List, Tuple

from src.core.tool.base import BaseTool, ToolRegistry
from src.core.tool.spec_schema import ToolSpecFile
from src.core.tool.spec_utils import get_tool_spec_by_name
from src.core.tool.tool_bundle import ToolBundle


class ToolResolver:
    def __init__(
        self,
        tool_registry: ToolRegistry,
        tool_specs: List[ToolSpecFile]
    ):
        self.tool_registry = tool_registry
        self.tool_specs = tool_specs

    def resolve_tool_names(self, tool_names: List[str]) -> Tuple[List[BaseTool], List[str]]:
        resolved_tools: List[BaseTool] = []
        errors: List[str] = []

        for tool_name in tool_names:
            spec = get_tool_spec_by_name(self.tool_specs, tool_name)
            if spec is None:
                errors.append(f"未找到工具描述文件: {tool_name}")
                continue

            if not self.tool_registry.has(tool_name):
                errors.append(f"未找到工具实现: {tool_name}")
                continue

            tool = self.tool_registry.get(tool_name)
            resolved_tools.append(tool)

        return resolved_tools, errors

    def resolve_bundle(self, bundle: ToolBundle) -> Tuple[ToolRegistry, List[str]]:
        resolved_registry = ToolRegistry()
        resolved_tools, errors = self.resolve_tool_names(bundle.tool_names)

        for tool in resolved_tools:
            resolved_registry.register(tool)

        return resolved_registry, errors

    def resolve_allowed_tools(self, allowed_tools: List[str]) -> Tuple[ToolRegistry, List[str]]:
        bundle = ToolBundle(
            bundle_id="runtime_bundle",
            tool_names=allowed_tools,
            description="runtime resolved tool bundle"
        )
        return self.resolve_bundle(bundle)

    def get_tool_specs_for_names(self, tool_names: List[str]) -> List[ToolSpecFile]:
        result: List[ToolSpecFile] = []

        for tool_name in tool_names:
            spec = get_tool_spec_by_name(self.tool_specs, tool_name)
            if spec is not None:
                result.append(spec)

        return result