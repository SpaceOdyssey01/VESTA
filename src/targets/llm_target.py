from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.targets.visibility import visible_tool_names


def load_yaml(path: str | Path) -> Dict[str, Any]:
    path = Path(path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class LLMTarget:
    def __init__(
        self,
        llm_config_path: str | Path = "configs/llm/gpt-5.4.yaml",
        max_repair_attempts: int = 1
    ):
        self.llm_config_path = llm_config_path
        self.llm_config = load_yaml(llm_config_path)
        self.max_repair_attempts = max_repair_attempts

    def respond(
        self,
        messages: List[Dict[str, str]],
        tool_bundle: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        raw_output = self._call_llm(messages)

        parsed = self._parse_or_repair(
            raw_output=raw_output,
            messages=messages
        )

        return self._normalize_response(
            parsed=parsed,
            raw_output=raw_output,
            tool_bundle=tool_bundle
        )

    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is required for target LLM.") from exc

        model = (
            self.llm_config.get("model")
            or self.llm_config.get("model_name")
            or self.llm_config.get("name")
        )

        if not model:
            raise ValueError(f"LLM config missing model/model_name/name: {self.llm_config_path}")

        api_key = self.llm_config.get("api_key")
        api_key_env = self.llm_config.get("api_key_env")

        if not api_key and api_key_env:
            api_key = os.getenv(api_key_env)

        if not api_key:
            api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DASHSCOPE_API_KEY")

        base_url = self.llm_config.get("base_url") or self.llm_config.get("api_base")
        temperature = float(self.llm_config.get("temperature", 0.2))

        client_kwargs: Dict[str, Any] = {}

        if api_key:
            client_kwargs["api_key"] = api_key

        if base_url:
            client_kwargs["base_url"] = base_url

        client = OpenAI(**client_kwargs)

        request = {
            "model": model,
            "temperature": temperature,
            "messages": messages
        }

        try:
            response = client.chat.completions.create(**request)
        except Exception as exc:
            message = str(exc).lower()
            if (
                "temperature" in message
                and (
                    "deprecated" in message
                    or "unsupported" in message
                    or "not support" in message
                    or "not accepted" in message
                )
            ):
                request.pop("temperature", None)
                response = client.chat.completions.create(**request)
            else:
                raise

        return response.choices[0].message.content or ""

    def _parse_or_repair(
        self,
        raw_output: str,
        messages: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        try:
            return self._parse_json_object(raw_output)
        except Exception:
            pass

        for _ in range(self.max_repair_attempts):
            repair_messages = messages + [
                {
                    "role": "assistant",
                    "content": raw_output
                },
                {
                    "role": "user",
                    "content": (
                        "Your previous response was invalid because it did not contain exactly one JSON object. "
                        "Please rewrite it as exactly ONE JSON object. "
                        "If you previously included multiple tool calls or combined a tool_call with a final_answer, choose only the single next immediate action. "
                        "If a tool should be called next, output only that one tool_call and wait for the tool result before continuing. "
                        "Use one of these schemas:\n"
                        "{\"response_type\":\"tool_call\",\"tool_name\":\"tool_name_here\",\"arguments\":{}}\n"
                        "or\n"
                        "{\"response_type\":\"final_answer\",\"content\":\"your response here\"}\n"
                        "Do not output markdown or extra text."
                    )
                }
            ]

            repaired_output = self._call_llm(repair_messages)

            try:
                return self._parse_json_object(repaired_output)
            except Exception:
                continue

        return {
            "response_type": "final_answer",
            "content": f"Unable to parse target output as valid JSON. Raw output: {raw_output[:500]}"
        }

    def _parse_json_object(self, text: str) -> Dict[str, Any]:
        text = text.strip()

        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text).strip()
            text = re.sub(r"```$", "", text).strip()

        json_objects = self._extract_json_objects(text)

        if len(json_objects) != 1:
            raise ValueError(
                f"Expected exactly one JSON object, but found {len(json_objects)}."
            )

        data = json.loads(json_objects[0])

        if not isinstance(data, dict):
            raise ValueError("Target output must be a JSON object.")

        return data
    
    def _extract_json_objects(self, text: str) -> List[str]:
        objects: List[str] = []

        start = None
        depth = 0
        in_string = False
        escape = False

        for index, char in enumerate(text):
            if escape:
                escape = False
                continue

            if char == "\\" and in_string:
                escape = True
                continue

            if char == '"':
                in_string = not in_string
                continue

            if in_string:
                continue

            if char == "{":
                if depth == 0:
                    start = index
                depth += 1

            elif char == "}":
                if depth > 0:
                    depth -= 1

                    if depth == 0 and start is not None:
                        objects.append(text[start:index + 1])
                        start = None

        return objects

    def _normalize_response(
        self,
        parsed: Dict[str, Any],
        raw_output: str,
        tool_bundle: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        response_type = parsed.get("response_type")

        if response_type not in {"tool_call", "final_answer"}:
            return {
                "response_type": "final_answer",
                "content": str(parsed),
                "raw_output": raw_output,
                "parse_status": "invalid_response_type"
            }

        if response_type == "final_answer":
            return {
                "response_type": "final_answer",
                "content": str(parsed.get("content", "")),
                "raw_output": raw_output,
                "parse_status": "ok"
            }

        tool_name = parsed.get("tool_name", "")
        arguments = parsed.get("arguments", {})

        if not isinstance(arguments, dict):
            arguments = {}

        available_tool_names = set()
        visible_tool_aliases: Dict[str, str] = {}

        if tool_bundle:
            available_tool_names = set(tool_bundle.get("tool_names", []))
            visible_tool_aliases = {
                visible: internal for internal, visible in
                visible_tool_names(tool_bundle.get("tool_specs", [])).items()
            }

        if tool_name in visible_tool_aliases:
            tool_name = visible_tool_aliases[tool_name]

        if available_tool_names and tool_name not in available_tool_names:
            return {
                "response_type": "final_answer",
                "content": f"Requested tool is not available: {tool_name}",
                "raw_output": raw_output,
                "parse_status": "tool_not_available",
                "requested_tool_name": tool_name,
                "available_tool_names": sorted(available_tool_names)
            }

        return {
            "response_type": "tool_call",
            "tool_name": tool_name,
            "arguments": arguments,
            "raw_output": raw_output,
            "parse_status": "ok"
        }


def build_llm_target(
    llm_config_path: str | Path = "configs/llm/gpt-5.4.yaml"
) -> LLMTarget:
    return LLMTarget(
        llm_config_path=llm_config_path
    )
