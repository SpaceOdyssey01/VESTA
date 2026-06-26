from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ToolSpecFile:
    tool_name: str
    description: str
    category: str = ""
    tool_type: str = "query"
    tool_mode: str = "simulated"
    risk_level: str = "low"
    requires_confirmation: bool = False
    input_schema: Dict[str, Any] = field(default_factory=dict)
    required_parameters: List[str] = field(default_factory=list)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    possible_risk_dimensions: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


@dataclass
class ToolManifest:
    manifest_id: str
    tools: List[ToolSpecFile] = field(default_factory=list)


@dataclass
class ToolSpecValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)


def validate_tool_spec_file(spec: ToolSpecFile) -> ToolSpecValidationResult:
    errors: List[str] = []

    if not spec.tool_name.strip():
        errors.append("tool_name不能为空")

    if not spec.description.strip():
        errors.append("description不能为空")

    if spec.tool_type not in ["query", "execution", "control", "analysis"]:
        errors.append("tool_type必须是query/execution/control/analysis之一")

    if spec.tool_mode not in ["simulated"]:
        errors.append("tool_mode必须是simulated")

    if spec.risk_level not in ["low", "medium", "high"]:
        errors.append("risk_level必须是low/medium/high之一")

    if not isinstance(spec.input_schema, dict):
        errors.append("input_schema必须是dict")

    if not isinstance(spec.output_schema, dict):
        errors.append("output_schema必须是dict")

    if not isinstance(spec.required_parameters, list):
        errors.append("required_parameters必须是list")

    return ToolSpecValidationResult(valid=len(errors) == 0, errors=errors)