#定义环境状态
from dataclasses import dataclass, field
from typing import Any, Dict, List

#当前整个环境状态
@dataclass
class EnvironmentState:
    data: Dict[str, Any] = field(default_factory=dict)

#某一步的环境快照，记录了当时的环境状态，可以用于回滚或者分析
@dataclass
class EnvironmentSnapshot:
    step_id: int
    state: Dict[str, Any] = field(default_factory=dict)

#环境更新结果，记录了更新是否成功、更新后的新状态、发生变化的键和错误信息
@dataclass
class EnvironmentUpdateResult:
    success: bool
    new_state: Dict[str, Any] = field(default_factory=dict)
    changed_keys: List[str] = field(default_factory=list)
    error_message: str = ""

#环境验证结果，记录了验证是否通过和错误信息列表
@dataclass
class EnvironmentValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)

#一个最基础的验证函数，检查环境状态是否符合规范，目前仅检查是否是dict类型，后续可以根据具体任务需求添加更多验证规则
def validate_environment_state(state: EnvironmentState) -> EnvironmentValidationResult:
    errors: List[str] = []

    if not isinstance(state.data, dict):
        errors.append("environment state必须是dict")

    return EnvironmentValidationResult(valid=len(errors) == 0, errors=errors)