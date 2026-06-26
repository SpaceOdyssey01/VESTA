#定义任务的数据结构
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

#定义任务的元数据结构，包括来源、难度、目标风险维度和标签
@dataclass
class TaskMetadata:
    source: str = ""
    difficulty: str = ""
    target_risk_dimensions: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

#定义单个任务Task的数据结构，包括任务ID、用户指令、环境信息、允许使用的工具列表和元数据
@dataclass
class Task:
    task_id: str
    user_instruction: str
    environment: Dict[str, Any]
    allowed_tools: List[str]
    metadata: TaskMetadata = field(default_factory=TaskMetadata)

#定义任务批次TaskBatch的数据结构，包括批次ID和任务列表
@dataclass
class TaskBatch:
    batch_id: str
    tasks: List[Task]

#定义任务加载结果TaskLoadResult的数据结构，包括加载是否成功、任务列表和消息
@dataclass
class TaskLoadResult:
    success: bool
    tasks: List[Task]
    message: str = ""

#定义任务验证结果TaskValidationResult的数据结构，包括验证是否通过和错误信息列表
@dataclass
class TaskValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)

#一个最基础的验证函数
def validate_task(task: Task) -> TaskValidationResult:
    errors: List[str] = []

    if not task.task_id.strip():
        errors.append("task_id不能为空")

    if not task.user_instruction.strip():
        errors.append("user_instruction不能为空")

    if not isinstance(task.environment, dict):
        errors.append("environment必须是dict")

    if not isinstance(task.allowed_tools, list):
        errors.append("allowed_tools必须是list")
    else:
        for tool_name in task.allowed_tools:
            if not isinstance(tool_name, str) or not tool_name.strip():
                errors.append("allowed_tools中的每个工具名都必须是非空字符串")
                break

    return TaskValidationResult(valid=len(errors) == 0, errors=errors)