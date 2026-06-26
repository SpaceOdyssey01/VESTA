import json
from pathlib import Path
from typing import Any, Dict, List

from src.core.task.schema import (
    Task,
    TaskBatch,
    TaskLoadResult,
    TaskMetadata,
    validate_task
)


def _build_task_from_dict(data: Dict[str, Any]) -> Task:
    metadata_dict = data.get("metadata", {})

    metadata = TaskMetadata(
        source=metadata_dict.get("source", ""),
        difficulty=metadata_dict.get("difficulty", ""),
        target_risk_dimensions=metadata_dict.get("target_risk_dimensions", []),
        tags=metadata_dict.get("tags", [])
    )

    task = Task(
        task_id=data.get("task_id", ""),
        user_instruction=data.get("user_instruction", ""),
        environment=data.get("environment", {}),
        allowed_tools=data.get("allowed_tools", []),
        metadata=metadata
    )

    return task
#从字典加载一个任务（备用）
def load_task_from_dict(data: Dict[str, Any]) -> TaskLoadResult:
    try:
        task = _build_task_from_dict(data)
        validation_result = validate_task(task)

        if not validation_result.valid:
            return TaskLoadResult(
                success=False,
                tasks=[],
                message="; ".join(validation_result.errors)
            )

        return TaskLoadResult(
            success=True,
            tasks=[task],
            message="任务加载成功"
        )
    except Exception as e:
        return TaskLoadResult(
            success=False,
            tasks=[],
            message=f"任务加载失败: {str(e)}"
        )

#从单个json文件加载一个任务，文件内容应该是一个符合Task结构的json对象，返回一个TaskLoadResult对象，包含加载是否成功、任务列表和消息等信息
def load_task_from_json(file_path: str) -> TaskLoadResult:
    try:
        path = Path(file_path)

        if not path.exists():
            return TaskLoadResult(
                success=False,
                tasks=[],
                message=f"文件不存在: {file_path}"
            )

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return load_task_from_dict(data)
    except Exception as e:
        return TaskLoadResult(
            success=False,
            tasks=[],
            message=f"读取任务文件失败: {str(e)}"
        )

#从字典列表加载多个任务（备用）
def load_tasks_from_dict_list(data_list: List[Dict[str, Any]]) -> TaskLoadResult:
    tasks: List[Task] = []
    errors: List[str] = []

    for index, data in enumerate(data_list):
        try:
            task = _build_task_from_dict(data)
            validation_result = validate_task(task)

            if not validation_result.valid:
                errors.append(f"第{index + 1}个任务不合法: {'; '.join(validation_result.errors)}")
                continue

            tasks.append(task)
        except Exception as e:
            errors.append(f"第{index + 1}个任务加载失败: {str(e)}")

    if errors:
        return TaskLoadResult(
            success=len(tasks) > 0,
            tasks=tasks,
            message=" | ".join(errors)
        )

    return TaskLoadResult(
        success=True,
        tasks=tasks,
        message="任务批量加载成功"
    )

#从一个json文件加载多个任务，文件内容应该是一个符合Task结构的json对象列表，返回一个TaskLoadResult对象，包含加载是否成功、任务列表和消息等信息
def load_tasks_from_json(file_path: str) -> TaskLoadResult:
    try:
        path = Path(file_path)

        if not path.exists():
            return TaskLoadResult(
                success=False,
                tasks=[],
                message=f"文件不存在: {file_path}"
            )

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            return TaskLoadResult(
                success=False,
                tasks=[],
                message="批量任务文件内容必须是list"
            )

        return load_tasks_from_dict_list(data)
    except Exception as e:
        return TaskLoadResult(
            success=False,
            tasks=[],
            message=f"读取批量任务文件失败: {str(e)}"
        )

#把任务列表打包成taskbatch
def build_task_batch(batch_id: str, tasks: List[Task]) -> TaskBatch:
    return TaskBatch(batch_id=batch_id, tasks=tasks)