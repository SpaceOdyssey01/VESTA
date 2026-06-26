#统一加载tool_specs目录
import os
from pathlib import Path
from typing import Dict, List

from src.core.tool.spec_loader import load_tool_spec_from_json
from src.core.tool.spec_schema import ToolSpecFile


class ToolSpecRegistry:
    def __init__(self, root_dir: str):
        # Normalize root_dir to an absolute path.
        # If the provided path is relative, first try relative to cwd; if not found,
        # resolve relative to the project root (two levels up from `src`).
        candidate = Path(root_dir)
        if not candidate.is_absolute():
            # try cwd
            candidate_cwd = Path(os.getcwd()) / root_dir
            if candidate_cwd.exists():
                candidate = candidate_cwd
            else:
                # resolve relative to project root: /.../X (parents[3] from this file -> project root)
                project_root = Path(__file__).resolve().parents[3]
                candidate_proj = project_root / root_dir
                candidate = candidate_proj

        self.root_dir = str(candidate)
        self._specs: Dict[str, ToolSpecFile] = {}

    def load_all(self) -> None:
        for dirpath, _, filenames in os.walk(self.root_dir):
            for filename in filenames:
                if not filename.endswith(".json"):
                    continue

                file_path = os.path.join(dirpath, filename)

                try:
                    spec = load_tool_spec_from_json(file_path)
                    self._specs[spec.tool_name] = spec
                except Exception as e:
                    print(f"[ToolSpecRegistry] 加载失败: {file_path} | error: {e}")

    def get_all_specs(self) -> List[ToolSpecFile]:
        return list(self._specs.values())

    def get_spec(self, tool_name: str) -> ToolSpecFile:
        if tool_name not in self._specs:
            raise ValueError(f"未找到工具spec: {tool_name}")
        return self._specs[tool_name]

    def has(self, tool_name: str) -> bool:
        return tool_name in self._specs

    def list_tool_names(self) -> List[str]:
        return list(self._specs.keys())