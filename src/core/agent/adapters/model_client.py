import json
from typing import Any, Dict, List, Optional

import requests


class OpenAICompatibleModelClient:
    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        timeout: int = 60,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model_name: str,
        temperature: float = 0.0,
    ) -> str:
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Content-Type": "application/json",
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            "temperature": temperature,
        }

        response = requests.post(
            url=url,
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()

        data = response.json()
        return self._extract_text(data)

    def _extract_text(self, data: Dict[str, Any]) -> str:
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("模型返回中没有choices字段")

        message = choices[0].get("message", {})
        content = message.get("content", "")

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        parts.append(item.get("text", ""))
            return "\n".join(parts).strip()

        return str(content)