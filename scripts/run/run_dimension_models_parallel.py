from __future__ import annotations

import argparse
import concurrent.futures
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Sequence


DATA_SCOPES = {
    "single_agent",
    "architecture_and_modules",
    "multi_agent_system",
    "external_environment",
    "interface_and_protocol",
}


@dataclass(frozen=True)
class RunTarget:
    dimension: str
    agent_scope: str | None = None


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_path(root: Path, path_text: str | Path) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return root / path


def rel_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root))
    except ValueError:
        return str(path)


def safe_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_") or "unknown"


def discover_dimensions(root: Path, agent_scope: str = "single_agent") -> List[str]:
    tool_config_root = root / "configs" / "tool_configs"
    configured_dimensions = {
        path.stem
        for path in tool_config_root.glob("*.yaml")
        if path.is_file()
    }

    task_root = root / "data" / agent_scope / "tasks"
    family_root = root / "data" / agent_scope / "families"
    task_dimensions = {
        path.name
        for path in task_root.iterdir()
        if path.is_dir()
    } if task_root.exists() else set()
    family_dimensions = {
        path.name
        for path in family_root.iterdir()
        if path.is_dir()
    } if family_root.exists() else set()

    dimensions = task_dimensions & family_dimensions

    config_filter = configured_dimensions
    if agent_scope in {
        "multi_agent_system",
        "external_environment",
        "interface_and_protocol",
    }:
        # These scopes intentionally use one shared tool config per scope.
        config_filter = None

    if config_filter is not None:
        dimensions &= config_filter

    if not dimensions:
        raise RuntimeError(
            "No runnable dimensions found. Expected matching entries under "
            f"data/{agent_scope}/tasks, data/{agent_scope}/families, and configs/tool_configs."
        )

    return sorted(dimensions)


def expand_dimension_token(token: str, root: Path) -> List[RunTarget]:
    if token in DATA_SCOPES:
        return [
            RunTarget(dimension=dimension, agent_scope=token)
            for dimension in discover_dimensions(root, agent_scope=token)
        ]

    return [RunTarget(dimension=token)]


def resolve_dimensions(args: argparse.Namespace, root: Path) -> List[RunTarget]:
    selected: List[RunTarget] = []

    if args.dimension:
        selected.extend(expand_dimension_token(args.dimension, root))

    if args.dimensions:
        for dimension in args.dimensions:
            selected.extend(expand_dimension_token(dimension, root))

    if args.all_dimensions:
        for scope in sorted(DATA_SCOPES):
            selected.extend(
                RunTarget(dimension=dimension, agent_scope=scope)
                for dimension in discover_dimensions(root, agent_scope=scope)
            )

    selected = list(dict.fromkeys(selected))

    if not selected:
        selected = [
            RunTarget(dimension=dimension)
            for dimension in discover_dimensions(root)
        ]

    return selected


def discover_model_configs(root: Path, llm_dir: str, llm_glob: str) -> List[str]:
    config_dir = resolve_path(root, llm_dir)

    if not config_dir.exists():
        raise FileNotFoundError(f"LLM config directory not found: {config_dir}")

    configs = sorted(path for path in config_dir.glob(llm_glob) if path.is_file())

    if not configs:
        raise FileNotFoundError(f"No LLM configs found under {config_dir} with glob {llm_glob}")

    return [rel_path(root, path) for path in configs]


def resolve_model_config(root: Path, llm_dir: str, model_text: str) -> str:
    model_path = Path(model_text)
    candidates = [
        resolve_path(root, model_path),
        resolve_path(root, Path(llm_dir) / model_text),
    ]

    if model_path.suffix != ".yaml":
        candidates.append(resolve_path(root, Path(llm_dir) / f"{model_text}.yaml"))

    for candidate in candidates:
        if candidate.exists():
            return rel_path(root, candidate)

    raise FileNotFoundError(
        f"Could not resolve model config '{model_text}'. "
        f"Use a path like configs/llm/gpt-4o-mini.yaml or a stem under {llm_dir}."
    )


def resolve_models(args: argparse.Namespace, root: Path) -> List[str]:
    selected: List[str] = []

    if args.target_llm_config:
        selected.append(resolve_model_config(root, args.llm_dir, args.target_llm_config))

    if args.models:
        selected.extend(
            resolve_model_config(root, args.llm_dir, model)
            for model in args.models
        )

    if args.all_target_models or not selected:
        selected.extend(discover_model_configs(root, args.llm_dir, args.llm_glob))

    return list(dict.fromkeys(selected))


def model_stem(model_config: str) -> str:
    return Path(model_config).stem


def build_model_cmd(
    python_bin: str,
    eval_script: Path,
    target: RunTarget,
    model_config: str,
    forwarded_args: Sequence[str],
) -> List[str]:
    cmd = [
        python_bin,
        str(eval_script),
        "--dimension",
        target.dimension,
        "--target-llm-config",
        model_config,
        *forwarded_args,
    ]

    if target.agent_scope and "--agent-scope" not in forwarded_args:
        cmd += ["--agent-scope", target.agent_scope]

    if "--continue-on-error" not in forwarded_args and "--fail-fast" not in forwarded_args:
        cmd += ["--continue-on-error"]

    return cmd


def run_model(cmd: Sequence[str], root: Path, log_path: Path) -> int:
    env = os.environ.copy()
    old_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(root) if not old_pythonpath else str(root) + os.pathsep + old_pythonpath

    log_path.parent.mkdir(parents=True, exist_ok=True)

    with log_path.open("w", encoding="utf-8") as log_file:
        log_file.write(">>> " + " ".join(cmd) + "\n\n")
        log_file.flush()

        process = subprocess.Popen(
            list(cmd),
            cwd=str(root),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        return process.wait()


def parse_args() -> tuple[argparse.Namespace, List[str]]:
    parser = argparse.ArgumentParser(
        description=(
            "Run one dimension eval process per dimension/model pair in parallel. "
            "Unknown arguments are forwarded to run_dimension_eval.py."
        )
    )

    parser.add_argument("--dimension", default=None)
    parser.add_argument("--dimensions", nargs="+", default=None)
    parser.add_argument("--all-dimensions", action="store_true")
    parser.add_argument("--models", nargs="+", default=None)
    parser.add_argument("--target-llm-config", default=None)
    parser.add_argument("--all-target-models", action="store_true")
    parser.add_argument("--llm-dir", default="configs/llm")
    parser.add_argument("--llm-glob", default="*.yaml")
    parser.add_argument("--max-workers", type=int, default=None)
    parser.add_argument("--log-dir", default=None)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--dry-run", action="store_true")

    args, forwarded_args = parser.parse_known_args()

    ignored_pipeline_only_args = {"--skip-score", "--skip-plot"}
    forwarded_args = [
        item for item in forwarded_args
        if item not in ignored_pipeline_only_args
    ]

    disallowed = {
        "--existing-run-dir": "single-run only",
        "--dimension": "handled by this wrapper",
        "--dimensions": "handled by this wrapper",
        "--all-dimensions": "handled by this wrapper",
        "--all-target-models": "handled by this wrapper",
        "--target-llm-config": "handled by this wrapper",
        "--run-id": "not used; outputs are written to outputs/results/<dimension>/<subtype>/<model>/",
    }

    for item, reason in disallowed.items():
        if item in forwarded_args:
            raise ValueError(f"{item} cannot be forwarded here; it is {reason}.")

    return args, forwarded_args


def main() -> None:
    args, forwarded_args = parse_args()
    root = project_root()
    targets = resolve_dimensions(args, root)
    models = resolve_models(args, root)

    job_count = len(targets) * len(models)
    max_workers = args.max_workers or job_count
    max_workers = max(1, min(max_workers, job_count))

    eval_script = root / "scripts" / "run" / "run_dimension_eval.py"
    if not eval_script.exists():
        raise FileNotFoundError(f"Eval script not found: {eval_script}")

    batch_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_dir = Path(args.log_dir).resolve() if args.log_dir else root / "runtime" / "logs" / "run_models" / batch_id

    jobs = []
    for target in targets:
        for model_config in models:
            cmd = build_model_cmd(
                python_bin=args.python,
                eval_script=eval_script,
                target=target,
                model_config=model_config,
                forwarded_args=forwarded_args,
            )
            log_path = log_dir / safe_name(target.agent_scope or "auto") / safe_name(target.dimension) / f"{safe_name(model_stem(model_config))}.log"
            jobs.append((target, model_config, cmd, log_path))

    print("Selected dimensions:")
    for target in targets:
        suffix = f" (agent_scope={target.agent_scope})" if target.agent_scope else ""
        print(f"- {target.dimension}{suffix}")

    print("Selected target models:")
    for model_config in models:
        print(f"- {model_config}")

    print(f"\nMax parallel workers: {max_workers}")
    print(f"Total jobs: {len(jobs)}")
    print(f"Logs directory: {log_dir}")
    print(f"Forwarded args: {' '.join(forwarded_args) if forwarded_args else '(none)'}")

    print("\nThis wrapper runs eval only. Run score_dimension_results.py and plot_dimension_scores.py after it finishes.")

    if args.dry_run:
        print("\nDry run commands:")
        for _, _, cmd, _ in jobs:
            print(" ".join(cmd))
        return

    started_at = time.time()
    failures = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_job = {
            executor.submit(run_model, cmd, root, log_path): (target, model_config, cmd, log_path)
            for target, model_config, cmd, log_path in jobs
        }

        for future in concurrent.futures.as_completed(future_to_job):
            target, model_config, _, log_path = future_to_job[future]
            job_name = f"{target.dimension}/{model_config}"
            try:
                return_code = future.result()
            except Exception as exc:
                failures.append((target.dimension, model_config, -1, log_path, str(exc)))
                print(f"[failed] {job_name}: {exc}  log={log_path}", flush=True)
                continue

            if return_code == 0:
                print(f"[done] {job_name}  log={log_path}", flush=True)
            else:
                failures.append((target.dimension, model_config, return_code, log_path, ""))
                print(f"[failed] {job_name}: exit={return_code}  log={log_path}", flush=True)

    elapsed = time.time() - started_at

    print(f"\nParallel model run finished in {elapsed:.1f}s.")
    print(f"Logs directory: {log_dir}")

    if failures:
        print("\nFailures:")
        for dimension, model_config, return_code, log_path, error in failures:
            suffix = f" error={error}" if error else ""
            print(f"- {dimension}/{model_config}: exit={return_code} log={log_path}{suffix}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
