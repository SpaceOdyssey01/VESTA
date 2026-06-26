from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Set


DEFAULT_AGENT_SCOPE = "single_agent"
DATA_SCOPES = [
    DEFAULT_AGENT_SCOPE,
    "architecture_and_modules",
    "multi_agent_system",
]

LEGACY_SEED_DIRS = {
    ("goal_norm_misalignment", "side_effect_negligence"): "side_sffect_negligence_seeds",
}


def scoped_data_root(project_root: Path, agent_scope: str = DEFAULT_AGENT_SCOPE) -> Path:
    return project_root / "data" / agent_scope


def family_root(project_root: Path, agent_scope: str = DEFAULT_AGENT_SCOPE) -> Path:
    return scoped_data_root(project_root, agent_scope) / "families"


def task_root(project_root: Path, agent_scope: str = DEFAULT_AGENT_SCOPE) -> Path:
    return scoped_data_root(project_root, agent_scope) / "tasks"


def legacy_family_root(project_root: Path) -> Path:
    return project_root / "data" / "families"


def legacy_task_root(project_root: Path) -> Path:
    return project_root / "data" / "tasks"


def scoped_family_roots(project_root: Path, preferred_scope: str = DEFAULT_AGENT_SCOPE) -> List[Path]:
    scopes = [preferred_scope] + [scope for scope in DATA_SCOPES if scope != preferred_scope]
    return [family_root(project_root, scope) for scope in scopes] + [legacy_family_root(project_root)]


def scoped_task_roots(project_root: Path, preferred_scope: str = DEFAULT_AGENT_SCOPE) -> List[Path]:
    scopes = [preferred_scope] + [scope for scope in DATA_SCOPES if scope != preferred_scope]
    return [task_root(project_root, scope) for scope in scopes] + [legacy_task_root(project_root)]


def seed_filenames(seed_filename: str) -> List[str]:
    names = [seed_filename]
    if seed_filename == "seeds_ch.json":
        names.append("seed_ch.json")
    return list(dict.fromkeys(names))


def family_path_for(
    project_root: Path,
    dimension: str,
    subtype: str,
    agent_scope: str = DEFAULT_AGENT_SCOPE,
) -> Path:
    candidates = [
        root / dimension / f"{subtype}.json"
        for root in scoped_family_roots(project_root, agent_scope)
    ]

    for path in candidates:
        if path.exists():
            return path

    return candidates[0]


def seed_path_for(
    project_root: Path,
    dimension: str,
    subtype: str,
    seed_filename: str = "seeds.json",
    agent_scope: str = DEFAULT_AGENT_SCOPE,
) -> Path:
    candidates: List[Path] = []
    for root in scoped_task_roots(project_root, agent_scope):
        for name in seed_filenames(seed_filename):
            candidates.append(root / dimension / f"{subtype}_seeds" / name)
        for name in seed_filenames(seed_filename):
            candidates.append(root / dimension / subtype / name)

        legacy_dir = LEGACY_SEED_DIRS.get((dimension, subtype))
        if legacy_dir:
            for name in seed_filenames(seed_filename):
                candidates.append(root / dimension / legacy_dir / name)

    for path in candidates:
        if path.exists():
            return path

    return candidates[0]


def list_dimension_dirs(root: Path) -> Set[str]:
    if not root.exists():
        return set()
    return {
        path.name
        for path in root.iterdir()
        if path.is_dir() and not path.name.startswith((".", "__"))
    }


def list_subtypes(
    project_root: Path,
    dimension: str,
    agent_scope: str = DEFAULT_AGENT_SCOPE,
) -> List[str]:
    roots = [
        root / dimension
        for root in scoped_family_roots(project_root, agent_scope)
    ]
    for root in roots:
        if root.exists():
            return sorted(path.stem for path in root.glob("*.json") if path.is_file())
    return []


def discover_data_dimensions(
    project_root: Path,
    agent_scope: str = DEFAULT_AGENT_SCOPE,
    configured_dimensions: Optional[Iterable[str]] = None,
) -> List[str]:
    task_dimensions = (
        set().union(*(list_dimension_dirs(root) for root in scoped_task_roots(project_root, agent_scope)))
    )
    family_dimensions = (
        set().union(*(list_dimension_dirs(root) for root in scoped_family_roots(project_root, agent_scope)))
    )
    dimensions = task_dimensions & family_dimensions
    if configured_dimensions is not None:
        dimensions &= set(configured_dimensions)
    return sorted(dimensions)
