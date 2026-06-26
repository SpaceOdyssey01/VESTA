from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# 定义工具规范、工具执行输入和工具执行结果等数据结构，以及工具输入验证和结果构建的辅助函数。这些定义和函数可以帮助我们在Agent执行工具时进行规范化的输入输出处理和错误处理。
@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    required_parameters: List[str] = field(default_factory=list)
    risk_level: str = "low"

# 工具执行输入包含工具名称、参数和环境状态等信息，工具执行结果包含执行是否成功、观察结果、错误信息、状态变化和风险标志等信息。工具输入验证函数检查输入的合法性，结果构建函数帮助我们快速构建成功或错误的执行结果。
@dataclass
class ToolExecutionInput:
    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    environment_state: Dict[str, Any] = field(default_factory=dict)

# 工具执行结果包含执行是否成功、观察结果、错误信息、状态变化和风险标志等信息。工具输入验证函数检查输入的合法性，结果构建函数帮助我们快速构建成功或错误的执行结果。
@dataclass
class ToolExecutionResult:
    success: bool
    observation: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    state_delta: Dict[str, Any] = field(default_factory=dict)
    risk_flags: List[str] = field(default_factory=list)
    execution_status: str = "success"

# 工具验证结果包含验证是否通过和错误信息等信息。工具输入验证函数检查输入的合法性，结果构建函数帮助我们快速构建成功或错误的执行结果。
@dataclass
class ToolValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)

# 工具输入验证函数检查输入的合法性，结果构建函数帮助我们快速构建成功或错误的执行结果。
def validate_tool_execution_input(
    execution_input: ToolExecutionInput,
    tool_spec: ToolSpec
) -> ToolValidationResult:
    errors: List[str] = []

    if execution_input.tool_name != tool_spec.name:
        errors.append("tool_name与tool_spec.name不一致")

    for param_name in tool_spec.required_parameters:
        if param_name not in execution_input.arguments:
            errors.append(f"缺少必需参数: {param_name}")

    return ToolValidationResult(valid=len(errors) == 0, errors=errors)


def build_tool_success_result(
    observation: Optional[Dict[str, Any]] = None,
    state_delta: Optional[Dict[str, Any]] = None,
    risk_flags: Optional[List[str]] = None
) -> ToolExecutionResult:
    return ToolExecutionResult(
        success=True,
        observation=observation or {},
        error_message="",
        state_delta=state_delta or {},
        risk_flags=risk_flags or [],
        execution_status="success"
    )


def build_tool_error_result(
    error_message: str,
    observation: Optional[Dict[str, Any]] = None,
    state_delta: Optional[Dict[str, Any]] = None,
    risk_flags: Optional[List[str]] = None,
    execution_status: str = "failed"
) -> ToolExecutionResult:
    return ToolExecutionResult(
        success=False,
        observation=observation or {},
        error_message=error_message,
        state_delta=state_delta or {},
        risk_flags=risk_flags or [],
        execution_status=execution_status
    )