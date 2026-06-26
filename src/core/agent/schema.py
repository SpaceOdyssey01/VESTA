#定义Agent的输出格式
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

#定义工具调用的数据结构，包括工具名称和参数
@dataclass
class ToolCall:
    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)

#定义Agent消息的数据结构，包括角色和内容，可用于多轮消息
@dataclass
class AgentMessage:
    role: str
    content: str

#定义Agent输出的数据结构，包括响应类型和内容
@dataclass
class AgentResponse:
    response_type: str
    content: str = ""
    tool_call: Optional[ToolCall] = None

#定义每一步Agent的输入数据结构，包括任务ID、用户指令、历史消息、环境状态和允许使用的工具列表
@dataclass
class AgentStepInput:
    task_id: str
    user_instruction: str
    history: List[Dict[str, Any]] = field(default_factory=list)
    environment_state: Dict[str, Any] = field(default_factory=dict)
    allowed_tools: List[str] = field(default_factory=list)

#定义每一步Agent的输出数据结构，包括步骤ID和响应内容
@dataclass
class AgentStepResult:
    step_id: int
    response: AgentResponse

#定义Agent验证结果的数据结构，包括验证是否通过和错误信息列表
@dataclass
class AgentValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)

#一个最基础的验证函数，后续agent的输出只能是tool_call或final_answer两种类型，如果是tool_call则必须包含tool_name，如果是final_answer则content不能为空
def validate_agent_response(response: AgentResponse) -> AgentValidationResult:
    errors: List[str] = []

    if response.response_type not in ["tool_call", "final_answer"]:
        errors.append("response_type必须是tool_call或final_answer")

    if response.response_type == "tool_call":
        if response.tool_call is None:
            errors.append("当response_type为tool_call时，tool_call不能为空")
        else:
            if not response.tool_call.tool_name.strip():
                errors.append("tool_call.tool_name不能为空")

    if response.response_type == "final_answer":
        if not response.content.strip():
            errors.append("当response_type为final_answer时，content不能为空")

    return AgentValidationResult(valid=len(errors) == 0, errors=errors)