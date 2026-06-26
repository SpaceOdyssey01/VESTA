from typing import List, Optional, Dict

from src.core.task.schema import Task

#查任务
def get_task_by_id(tasks: List[Task], task_id: str) -> Optional[Task]:
    for task in tasks:
        if task.task_id == task_id:
            return task
    return None

#按风险维度筛选
def filter_tasks_by_risk_dimension(tasks: List[Task], risk_dimension: str) -> List[Task]:
    result: List[Task] = []

    for task in tasks:
        if risk_dimension in task.metadata.target_risk_dimensions:
            result.append(task)

    return result

#按标签筛选
def filter_tasks_by_tag(tasks: List[Task], tag: str) -> List[Task]:
    result: List[Task] = []

    for task in tasks:
        if tag in task.metadata.tags:
            result.append(task)

    return result

#按工具筛选
def filter_tasks_by_tool(tasks: List[Task], tool_name: str) -> List[Task]:
    result: List[Task] = []

    for task in tasks:
        if tool_name in task.allowed_tools:
            result.append(task)

    return result

#按风险维度分组
def group_tasks_by_risk_dimension(tasks: List[Task]) -> Dict[str, List[Task]]:
    result: Dict[str, List[Task]] = {}

    for task in tasks:
        for risk in task.metadata.target_risk_dimensions:
            if risk not in result:
                result[risk] = []
            result[risk].append(task)

    return result

#按标签分组
def group_tasks_by_tag(tasks: List[Task]) -> Dict[str, List[Task]]:
    result: Dict[str, List[Task]] = {}

    for task in tasks:
        for tag in task.metadata.tags:
            if tag not in result:
                result[tag] = []
            result[tag].append(task)

    return result

#统计每个风险维度的任务数量
def count_tasks_by_risk_dimension(tasks: List[Task]) -> Dict[str, int]:
    result: Dict[str, int] = {}

    for task in tasks:
        for risk in task.metadata.target_risk_dimensions:
            result[risk] = result.get(risk, 0) + 1

    return result

#统计每个标签的任务数量
def count_tasks_by_tool(tasks: List[Task]) -> Dict[str, int]:
    result: Dict[str, int] = {}

    for task in tasks:
        for tool in task.allowed_tools:
            result[tool] = result.get(tool, 0) + 1

    return result