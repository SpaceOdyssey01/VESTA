from typing import Dict, List, Optional

from src.core.tool.spec_schema import ToolSpecFile


def get_tool_spec_by_name(specs: List[ToolSpecFile], tool_name: str) -> Optional[ToolSpecFile]:
    for spec in specs:
        if spec.tool_name == tool_name:
            return spec
    return None


def filter_tool_specs_by_mode(specs: List[ToolSpecFile], tool_mode: str) -> List[ToolSpecFile]:
    return [spec for spec in specs if spec.tool_mode == tool_mode]


def filter_tool_specs_by_risk_level(specs: List[ToolSpecFile], risk_level: str) -> List[ToolSpecFile]:
    return [spec for spec in specs if spec.risk_level == risk_level]


def filter_tool_specs_by_dimension(specs: List[ToolSpecFile], risk_dimension: str) -> List[ToolSpecFile]:
    result: List[ToolSpecFile] = []
    for spec in specs:
        if risk_dimension in spec.possible_risk_dimensions:
            result.append(spec)
    return result


def group_tool_specs_by_category(specs: List[ToolSpecFile]) -> Dict[str, List[ToolSpecFile]]:
    result: Dict[str, List[ToolSpecFile]] = {}
    for spec in specs:
        if spec.category not in result:
            result[spec.category] = []
        result[spec.category].append(spec)
    return result