#框架主体：Runner层，负责执行Agent并管理整个运行过程，包括环境状态、历史记录、日志记录和评估等功能
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from src.core.agent.base import BaseAgent
from src.core.agent.schema import AgentStepInput
from src.core.env.schema import EnvironmentState
from src.core.env.base import BaseEnvironment
from src.core.task.schema import Task
from src.core.tool.base import ToolRegistry
from src.core.tool.schema import ToolExecutionInput


class BaseRunner(ABC):
    @abstractmethod
    def run(self, task: Task) -> Dict[str, Any]:
        pass

# AgentRunner是BaseRunner的一个具体实现，负责执行单个Agent完成一个任务。它在每一步根据当前环境状态和历史记录调用agent生成响应，根据响应类型执行工具或记录最终答案，并更新环境状态和历史记录。同时它还支持日志记录和评估功能。
class AgentRunner(BaseRunner):
    #初始化函数，接受agent实例、工具注册表、日志记录器、评估器和最大步骤数等参数，并进行赋值
    def __init__(
        self,
        agent: BaseAgent,
        tool_registry: ToolRegistry,
        logger: Optional[Any] = None,
        evaluator: Optional[Any] = None,
        max_steps: int = 10
    ):
        self.agent = agent
        self.tool_registry = tool_registry
        self.logger = logger
        self.evaluator = evaluator
        self.max_steps = max_steps
    #核心函数，每一步根据当前环境状态和历史记录调用agent生成响应，根据响应类型执行工具或记录最终答案，并更新环境状态和历史记录。同时它还支持日志记录和评估功能。
    def run(self, task: Task) -> Dict[str, Any]:
        self.agent.reset()

        env = BaseEnvironment(task.environment)
        history: List[Dict[str, Any]] = []
        final_answer = ""
        status = "unfinished"

        if self.logger is not None:
            self.logger.log_run_start(
                {
                    "task_id": task.task_id,
                    "agent_name": self.agent.get_name(),
                    "max_steps": self.max_steps
                }
            )
        #核心循环step loop，每一步根据当前环境状态和历史记录调用agent生成响应，根据响应类型执行工具或记录最终答案，并更新环境状态和历史记录
        for step_id in range(1, self.max_steps + 1):
            step_input = AgentStepInput(
                task_id=task.task_id,
                user_instruction=task.user_instruction,
                history=history,
                environment_state=env.get_state(),
                allowed_tools=task.allowed_tools
            )
            #调用agent的act方法，根据当前步骤输入生成响应，响应可以是调用工具的指令也可以是最终答案
            agent_response = self.agent.act(step_input)

            step_record: Dict[str, Any] = {
                "step_id": step_id,
                "agent_response": self._serialize_agent_response(agent_response),
                "tool_result": None,
                "environment_state": dict(env.get_state())
            }
            #根据agent的响应类型进行处理，如果是final_answer则记录最终答案并结束，如果是tool_call则检查工具合法性并执行工具，记录工具结果和新的环境状态
            if agent_response.response_type == "final_answer":
                final_answer = agent_response.content
                status = "finished"

                if self.logger is not None:
                    self.logger.log_step(step_record)

                break

            tool_name = agent_response.tool_call.tool_name

            if tool_name not in task.allowed_tools:
                status = "failed"
                step_record["tool_result"] = {
                    "success": False,
                    "observation": {},
                    "error_message": f"工具{tool_name}不在allowed_tools中"
                }

                if self.logger is not None:
                    self.logger.log_step(step_record)

                break

            if not self.tool_registry.has(tool_name):
                status = "failed"
                step_record["tool_result"] = {
                    "success": False,
                    "observation": {},
                    "error_message": f"工具{tool_name}未注册"
                }

                if self.logger is not None:
                    self.logger.log_step(step_record)

                break

            tool = self.tool_registry.get(tool_name)
            #调用工具
            execution_input = ToolExecutionInput(
                tool_name=tool_name,
                arguments=agent_response.tool_call.arguments,
                environment_state=env.get_hidden_state()
            )

            tool_result = tool.execute(execution_input)

            step_record["tool_result"] = {
                "success": tool_result.success,
                "observation": tool_result.observation,
                "error_message": tool_result.error_message
            }

            if self.logger is not None:
                self.logger.log_step(step_record)
            #根据工具执行结果更新环境状态，如果工具执行失败则记录失败信息并结束
            history.append(
                {
                    "step_id": step_id,
                    "agent_response": step_record["agent_response"],
                    "tool_result": step_record["tool_result"]
                }
            )

        if status == "unfinished":
            status = "max_steps_exceeded"
        #跑完做评测
        evaluation_result = None
        if self.evaluator is not None:
            evaluation_result = self.evaluator.evaluate(
                task=task,
                history=history,
                final_answer=final_answer,
                status=status
            )
        #最终结果包括任务ID、agent名称、状态、最终答案、历史记录和评测结果等信息，并通过日志记录器记录整个运行过程的结果
        result = {
            "task_id": task.task_id,
            "agent_name": self.agent.get_name(),
            "status": status,
            "final_answer": final_answer,
            "history": history,
            "evaluation_result": evaluation_result
        }

        if self.logger is not None:
            self.logger.log_run_end(result)

        return result

    def _serialize_agent_response(self, agent_response) -> Dict[str, Any]:
        if agent_response.response_type == "final_answer":
            return {
                "response_type": "final_answer",
                "content": agent_response.content
            }

        return {
            "response_type": "tool_call",
            "tool_call": {
                "tool_name": agent_response.tool_call.tool_name,
                "arguments": agent_response.tool_call.arguments
            }
        }