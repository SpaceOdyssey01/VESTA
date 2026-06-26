#表示一轮任务开放哪些工具
from dataclasses import dataclass, field
from typing import List

@dataclass
class ToolBundle:
    bundle_id: str
    tool_names: List[str] = field(default_factory=list)
    description: str = ""