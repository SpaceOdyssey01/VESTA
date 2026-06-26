#定义一个基础的日志记录器
from abc import ABC, abstractmethod
from typing import Any, Dict, List

#定义统一接口的日志记录器，支持记录运行开始信息、每一步的记录和运行结束结果等功能，具体实现可以根据需要进行扩展，比如记录到文件、数据库或者远程服务器等
class BaseLogger(ABC):
    @abstractmethod
    def log_run_start(self, info: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def log_step(self, step_record: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def log_run_end(self, result: Dict[str, Any]) -> None:
        pass

#把数据存在内存里，包括运行开始信息、每一步的轨迹记录和运行结束结果等，可以通过get_trace方法获取整个运行过程的完整记录，reset方法可以清空所有记录以便进行新的运行
class InMemoryLogger(BaseLogger):
    def __init__(self):
        self.run_info: Dict[str, Any] = {}
        self.steps: List[Dict[str, Any]] = []
        self.result: Dict[str, Any] = {}

    def log_run_start(self, info: Dict[str, Any]) -> None:
        self.run_info = dict(info)

    def log_step(self, step_record: Dict[str, Any]) -> None:
        self.steps.append(dict(step_record))

    def log_run_end(self, result: Dict[str, Any]) -> None:
        self.result = dict(result)

    def get_trace(self) -> Dict[str, Any]:
        return {
            "run_info": self.run_info,
            "steps": self.steps,
            "result": self.result
        }

    def reset(self) -> None:
        self.run_info = {}
        self.steps = []
        self.result = {}