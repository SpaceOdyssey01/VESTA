from typing import Protocol

from src.core.agent.base import BaseAgent
from src.core.agent.parser import parse_agent_output
from src.core.agent.prompt_builder import (
    build_agent_system_prompt,
    build_agent_user_prompt,
)
from src.core.agent.schema import AgentResponse, AgentStepInput
from src.core.tool.base import ToolRegistry


class ModelClientProtocol(Protocol):
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model_name: str,
        temperature: float = 0.0,
    ) -> str:
        ...


class LLMAgent(BaseAgent):
    def __init__(
        self,
        tool_registry: ToolRegistry,
        model_client: ModelClientProtocol,
        model_name: str = "default-llm",
        temperature: float = 0.0,
        name: str = "llm_agent",
    ):
        super().__init__(name=name)
        self.tool_registry = tool_registry
        self.model_client = model_client
        self.model_name = model_name
        self.temperature = temperature

    def act(self, step_input: AgentStepInput) -> AgentResponse:
        system_prompt = build_agent_system_prompt()
        user_prompt = build_agent_user_prompt(
            step_input=step_input,
            tool_registry=self.tool_registry,
        )

        raw_output = self.model_client.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_name=self.model_name,
            temperature=self.temperature,
        )

        return parse_agent_output(raw_output)