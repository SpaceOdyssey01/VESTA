#把模型输出解析成AgentResponse
import json
from typing import Any, Dict

from src.core.agent.schema import AgentResponse, ToolCall

def _safe_json_loads(text: str) -> Dict[str, Any]:
    text = text.strip()

    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    if text.startswith("```"):
        text = text[len("```"):].strip()
    if text.endswith("```"):
        text = text[:-3].strip()

    try:
        return json.loads(text)
    except Exception:
        return {}

def parse_agent_output(output_text: str) -> AgentResponse:
    """
    解析模型输出，转换成 AgentResponse

    支持两种格式：

    1. JSON格式（推荐）
    {
        "response_type": "tool_call",
        "tool_name": "...",
        "arguments": {...}
    }

    2. final_answer
    {
        "response_type": "final_answer",
        "content": "..."
    }
    """

    data = _safe_json_loads(output_text)

    # ========= 情况1：解析成功 =========
    if data:
        response_type = data.get("response_type")

        if response_type == "tool_call":
            return AgentResponse(
                response_type="tool_call",
                tool_call=ToolCall(
                    tool_name=data.get("tool_name", ""),
                    arguments=data.get("arguments", {})
                )
            )

        if response_type == "final_answer":
            return AgentResponse(
                response_type="final_answer",
                content=data.get("content", "")
            )

    # ========= 情况2：解析失败 → fallback =========

    # 简单规则 fallback（避免模型输出不规范直接崩）
    if "tool_call" in output_text or "call" in output_text:
        return AgentResponse(
            response_type="final_answer",
            content="模型输出解析失败（疑似工具调用未规范）"
        )

    return AgentResponse(
        response_type="final_answer",
        content=output_text.strip()
    )