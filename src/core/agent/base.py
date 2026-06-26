#定义agent的抽象基类
from abc import ABC, abstractmethod
from typing import List

from src.core.agent.schema import AgentStepInput, AgentResponse


class BaseAgent(ABC):
    def __init__(self, name: str = "base_agent"):
        self.name = name
    #核心函数，每一步根据输入生成响应，响应可以是调用工具的指令也可以是最终答案
    @abstractmethod
    def act(self, step_input: AgentStepInput) -> AgentResponse:
        pass
    #重置函数，在每个新任务开始时调用，可以清理memory,cache,internal state历史状态
    def reset(self):
        pass
    #获取agent名称，主要用于日志记录和调试
    def get_name(self) -> str:
        return self.name