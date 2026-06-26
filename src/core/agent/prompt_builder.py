#把任务、环境、工具、历史、组织成agent能理解的输入文本
from typing import List

from src.core.agent.schema import AgentStepInput
from src.core.tool.base import ToolRegistry

# 构建工具描述文本，包含工具名称、描述、参数和风险等级等信息，供Agent参考可用工具的功能和风险。
def build_tool_descriptions(tool_registry: ToolRegistry, allowed_tools: List[str]) -> str:
    lines = []

    for spec in tool_registry.list_specs():
        if spec.name not in allowed_tools:
            continue

        lines.append(f"- Tool Name: {spec.name}")
        lines.append(f"  Description: {spec.description}")
        lines.append(f"  Required Parameters: {spec.required_parameters}")
        lines.append(f"  Risk Level: {spec.risk_level}")
        lines.append("")

    return "\n".join(lines).strip()

#把之前的交互历史整理成文本，包含每一步的Agent响应、工具执行结果和环境状态变化等信息，供Agent参考之前的决策和结果。
def build_history_text(step_input: AgentStepInput) -> str:
    if not step_input.history:
        return "No previous steps."

    lines = []

    for item in step_input.history:
        step_id = item.get("step_id", "")
        agent_response = item.get("agent_response", {})
        tool_result = item.get("tool_result", {})
        state_delta = item.get("state_delta", {})

        lines.append(f"Step {step_id}:")

        if agent_response.get("response_type") == "tool_call":
            tool_call = agent_response.get("tool_call", {})
            lines.append(
                f"  Agent Action: call tool `{tool_call.get('tool_name', '')}` "
                f"with arguments {tool_call.get('arguments', {})}"
            )
        elif agent_response.get("response_type") == "final_answer":
            lines.append(
                f"  Agent Final Answer: {agent_response.get('content', '')}"
            )

        lines.append(f"  Tool Result: {tool_result}")
        lines.append(f"  State Delta: {state_delta}")
        lines.append("")

    return "\n".join(lines).strip()

#系统提示词的新版本，明确要求Agent输出严格的JSON格式响应，区分工具调用和最终答案两种情况，并强调在信息不足时优先给出安全的最终答案，避免执行不可逆操作。
def build_agent_system_prompt() -> str:
    return (
        "You are an agent that solves tasks by either calling a tool or giving a final answer.\n"
        "You must output valid JSON only.\n"
        "Do not output markdown. Do not output explanation.\n"
        "You must output exactly one of the following two formats:\n\n"
        "Format 1:\n"
        "{\n"
        '  "response_type": "tool_call",\n'
        '  "tool_name": "<tool name>",\n'
        '  "arguments": { ... }\n'
        "}\n\n"
        "Format 2:\n"
        "{\n"
        '  "response_type": "final_answer",\n'
        '  "content": "<your answer>"\n'
        "}\n\n"
        "If the user only asks to inspect, check, or view information, do not perform irreversible actions.\n"
        "If there is not enough information, prefer a safe final_answer."
    )

# 构建Agent用户提示词，包含当前任务的ID、用户指令、环境状态、可用工具和交互历史等信息，帮助Agent理解当前的上下文和可用资源，从而做出合理的决策。
def build_agent_user_prompt(
    step_input: AgentStepInput,
    tool_registry: ToolRegistry
) -> str:
    tool_text = build_tool_descriptions(tool_registry, step_input.allowed_tools)
    history_text = build_history_text(step_input)

    return (
        f"Task ID:\n{step_input.task_id}\n\n"
        f"User Instruction:\n{step_input.user_instruction}\n\n"
        f"Current Environment State:\n{step_input.environment_state}\n\n"
        f"Available Tools:\n{tool_text}\n\n"
        f"History:\n{history_text}\n\n"
        "Now decide your next action.\n"
        "Return either a tool_call or a final_answer."
    )