#把任务对象保存回jsonimport json
from pathlib import Path
from typing import List

from src.core.task.schema import Task, TaskBatch

#把任务对象转换成字典，方便保存成json格式
def _task_to_dict(task: Task) -> dict:
    return {
        "task_id": task.task_id,
        "user_instruction": task.user_instruction,
        "environment": task.environment,
        "allowed_tools": task.allowed_tools,
        "metadata": {
            "source": task.metadata.source,
            "difficulty": task.metadata.difficulty,
            "target_risk_dimensions": task.metadata.target_risk_dimensions,
            "tags": task.metadata.tags
        }
    }

#保存单个任务
def save_task_to_json(task: Task, file_path: str) -> None:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = _task_to_dict(task)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

#保存任务列表
def save_tasks_to_json(tasks: List[Task], file_path: str) -> None:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = [_task_to_dict(task) for task in tasks]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

#保存taskbatch
def save_task_batch_to_json(task_batch: TaskBatch, file_path: str) -> None:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "batch_id": task_batch.batch_id,
        "tasks": [_task_to_dict(task) for task in task_batch.tasks]
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)