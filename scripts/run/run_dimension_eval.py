from __future__ import annotations

import sys
from pathlib import Path

# Resolve from this file so the runner works after the project is moved.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import concurrent.futures
import importlib
import inspect
import json
import traceback
from typing import Any, Dict, List, Optional, Tuple

from src.core.data_paths import family_path_for, seed_path_for
from src.core.instance_adapter import normalize_instance


DEFAULT_DIMENSION = "autonomy_authority_failure"
AGENT_SCOPES = {"single_agent", "architecture_and_modules", "multi_agent_system", "external_environment", "interface_and_protocol"}

DIMENSION_SUBTYPES = {
    "autonomy_authority_failure": [
        "unauthorized_decision",
        "privilege_escalation",
        "dangerous_action_execution",
        "single_agent_cascade"
    ],
    "goal_norm_misalignment": [
        "reward_hacking",
        "side_effect_negligence",
        "objective_drift"
    ],
    "interaction_understanding_failure": [
        "intent_misinterpretation",
        "sycophantic_compliance"
    ],
    "supervision_control_failure": [
        "interruption_failure",
        "insufficient_oversight",
        "correction_resistance_or_delay",
        "audit_attribution_difficulty"
    ],
    "robustness_generalization_failure": [
        "adversarial_inducement_vulnerability",
        "long_horizon_task_instability",
        "misleading_context_vulnerability"
    ],
    "input_perception_risk": [
        "instruction_injection",
        "information_pollution"
    ],
    "memory_module_risk": [
        "memory_pollution",
        "context_hijacking",
        "summary_distortion"
    ],
    "reasoning_planning_risk": [
        "goal_decomposition_distortion",
        "constraint_omission",
        "risk_misassessment",
        "verification_failure"
    ],
    "action_tool_calling_risk": [
        "call_misjudgment",
        "permission_overreach",
        "tool_result_misuse",
        "system_brake_failure"
    ],
    "collective_cognition_distortion": [
        "information_integration_failure",
        "conformity_bias",
        "collective_false_consensus",
    ],
    "coordination_order_disruption": [
        "role_drift",
        "coordination_drift",
        "shared_memory_distortion",
    ],
    "coalition_power_imbalance": [
        "coalition_hijacking",
        "resource_capture",
        "authority_concentration",
    ],
    "interaction_chain_compromise": [
        "collaboration_content_pollution",
        "member_impersonation",
        "communication_bias",
        "intra_group_cascade",
    ],
    "group_pressure_manipulation": [
        "social_pressure",
        "opinion_manipulation",
        "false_majority_signal"
    ],
    "external_content_pollution": ["indirect_injection", "content_misdirection", "multimodal_pollution"],
    "external_state_distortion": ["state_misreporting", "action_feedback_distortion"],
    "external_resource_failure": ["knowledge_source_poisoning", "service_resource_compromise", "device_environment_compromise"],
    "real_world_consequence_amplification": ["data_asset_damage", "sensitive_information_leakage", "physical_risk_realization"],
    "open_world_residual_risk": ["unknown_carrier", "abnormal_context", "compositional_risk"],
    "interface_semantic_pollution": ["description_pollution", "schema_pollution", "return_semantic_pollution"],
    "identity_authorization_confusion": ["interface_service_impersonation", "authorization_misbinding", "delegation_overreach"],
    "protocol_semantic_mismatch": ["message_mismatch", "state_mismatch", "cross_protocol_mismatch"],
    "capability_version_instability": ["capability_drift", "composition_drift", "version_instability"]
}

RUNNER_CANDIDATES = [
    ("src.runners.dimension_runner", "DimensionRunner")
]

RUN_METHOD_CANDIDATES = [
    "run_instance",
    "run",
    "evaluate_instance",
    "evaluate"
]


def resolve_path(path_text: str | Path) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def safe_path_part(text: Any) -> str:
    value = str(text or "unknown").strip()
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)
    safe = "_".join(part for part in safe.split("_") if part)
    return safe or "unknown"


def path_agent_scope(path: Path) -> str:
    parts = list(path.parts)
    if "data" in parts:
        data_index = parts.index("data")
        if data_index + 1 < len(parts) and parts[data_index + 1] in AGENT_SCOPES:
            return parts[data_index + 1]
    return "single_agent"


def partition_dir(output_root: Path, agent_scope: str, dimension: str, subtype: str, model: str) -> Path:
    return output_root / safe_path_part(agent_scope) / safe_path_part(dimension) / safe_path_part(subtype) / safe_path_part(model)


def write_partitioned_outputs(output_root: Path, dimension: str, results: List[Dict[str, Any]], errors: List[Dict[str, Any]]) -> None:
    grouped_results: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    grouped_errors: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}

    for result in results:
        agent_scope = safe_path_part(result.get("agent_scope") or result.get("data_scope") or "single_agent")
        subtype = safe_path_part(result.get("risk_subtype") or result.get("subtype"))
        model = safe_path_part(result.get("target_model") or get_model_name(result.get("target_llm_config", "")))
        grouped_results.setdefault((agent_scope, subtype, model), []).append(result)

    for error in errors:
        agent_scope = safe_path_part(error.get("agent_scope") or error.get("data_scope") or "single_agent")
        subtype = safe_path_part(error.get("subtype") or error.get("risk_subtype"))
        model = safe_path_part(error.get("target_model") or get_model_name(error.get("target_llm_config", "")))
        grouped_errors.setdefault((agent_scope, subtype, model), []).append(error)

    partitions = sorted(set(grouped_results) | set(grouped_errors))

    manifests: Dict[str, Dict[str, Any]] = {}
    aggregate_manifest = {
        "dimension": dimension,
        "output_dir": str(output_root),
        "partitions": []
    }

    for agent_scope, subtype, model in partitions:
        scope_dimension_dir = output_root / safe_path_part(agent_scope) / safe_path_part(dimension)
        manifest = manifests.setdefault(
            agent_scope,
            {
                "agent_scope": agent_scope,
                "dimension": dimension,
                "output_dir": str(scope_dimension_dir),
                "partitions": []
            }
        )
        part_dir = partition_dir(output_root, agent_scope, dimension, subtype, model)
        part_results = grouped_results.get((agent_scope, subtype, model), [])
        part_errors = grouped_errors.get((agent_scope, subtype, model), [])
        save_json(part_dir / "results.json", part_results)
        save_json(part_dir / "errors.json", part_errors)
        partition_record = {
            "agent_scope": agent_scope,
            "risk_subtype": subtype,
            "target_model": model,
            "num_results": len(part_results),
            "num_errors": len(part_errors),
            "results_json": str(part_dir / "results.json"),
            "errors_json": str(part_dir / "errors.json")
        }
        manifest["partitions"].append(partition_record)
        aggregate_manifest["partitions"].append(partition_record)

    for agent_scope, manifest in manifests.items():
        dimension_dir = output_root / safe_path_part(agent_scope) / safe_path_part(dimension)
        save_json(dimension_dir / "partition_manifest.json", manifest)
    save_json(output_root / "partition_manifest.json", aggregate_manifest)


def case_key(
    item: Dict[str, Any],
    fallback_subtype: Optional[str] = None,
    fallback_target_llm_config: Optional[str] = None,
    fallback_authority_mode: Optional[str] = None,
    fallback_instance_id: Optional[str] = None
) -> Tuple[str, str, str, str]:
    subtype = (
        item.get("risk_subtype")
        or item.get("subtype")
        or fallback_subtype
        or ""
    )
    target_llm_config = (
        item.get("target_llm_config")
        or fallback_target_llm_config
        or ""
    )
    authority_mode = (
        item.get("authority_mode")
        or fallback_authority_mode
        or ""
    )
    instance_id = (
        item.get("instance_id")
        or fallback_instance_id
        or ""
    )

    return subtype, target_llm_config, authority_mode, instance_id


def expand_subtypes(dimension: str, subtypes: List[str]) -> List[str]:
    if not subtypes or "all" in subtypes:
        if dimension not in DIMENSION_SUBTYPES:
            raise ValueError(f"No default subtype list configured for dimension: {dimension}")
        return DIMENSION_SUBTYPES[dimension]
    return subtypes


def get_family_path(dimension: str, subtype: str, agent_scope: str = "single_agent") -> Path:
    return family_path_for(PROJECT_ROOT, dimension, subtype, agent_scope=agent_scope)


def seed_filenames(seed_filename: str) -> List[str]:
    names = [seed_filename]

    if seed_filename == "seeds_ch.json":
        names.append("seed_ch.json")

    return list(dict.fromkeys(names))


def get_seed_path(dimension: str, subtype: str, seed_filename: str = "seeds.json", agent_scope: str = "single_agent") -> Path:
    return seed_path_for(PROJECT_ROOT, dimension, subtype, seed_filename, agent_scope=agent_scope)


def load_instances(seed_path: Path) -> List[Dict[str, Any]]:
    data = load_json(seed_path)

    if isinstance(data, list):
        return [normalize_instance(item) for item in data]

    if isinstance(data, dict) and isinstance(data.get("instances"), list):
        return [normalize_instance(item) for item in data["instances"]]

    if isinstance(data, dict) and isinstance(data.get("tasks"), list):
        return [normalize_instance(item) for item in data["tasks"]]

    raise ValueError(f"Cannot find instances/tasks list in seed file: {seed_path}")


def load_runner_class():
    errors = []

    for module_name, class_name in RUNNER_CANDIDATES:
        try:
            module = importlib.import_module(module_name)
            runner_cls = getattr(module, class_name)
            return runner_cls
        except Exception as e:
            errors.append(f"{module_name}.{class_name}: {type(e).__name__}: {e}")

    raise ImportError(
        "Cannot import autonomy authority runner class. Tried:\n"
        + "\n".join(errors)
        + "\n\nPlease edit RUNNER_CANDIDATES in scripts/run_dimension_eval.py "
        + "to match your actual runner module/class name."
    )


def filter_kwargs_for_callable(func: Any, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    signature = inspect.signature(func)
    params = signature.parameters

    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return kwargs

    return {
        key: value
        for key, value in kwargs.items()
        if key in params
    }


def instantiate_runner(runner_cls: Any, kwargs: Dict[str, Any]) -> Any:
    try:
        filtered = filter_kwargs_for_callable(runner_cls, kwargs)
        return runner_cls(**filtered)
    except TypeError:
        return runner_cls()


def find_run_method(runner: Any):
    for method_name in RUN_METHOD_CANDIDATES:
        method = getattr(runner, method_name, None)
        if callable(method):
            return method_name, method

    raise AttributeError(
        f"Runner {runner.__class__.__name__} has no supported run method. "
        f"Tried: {RUN_METHOD_CANDIDATES}"
    )


def call_runner_method(method: Any, kwargs: Dict[str, Any]) -> Any:
    filtered = filter_kwargs_for_callable(method, kwargs)
    return method(**filtered)


def list_target_model_configs(
    all_target_models: bool,
    target_llm_config: str,
    llm_dir: str,
    llm_glob: str
) -> List[str]:
    if not all_target_models:
        return [target_llm_config]

    llm_path = resolve_path(llm_dir)

    if not llm_path.exists():
        raise FileNotFoundError(f"LLM config dir not found: {llm_path}")

    configs = sorted(llm_path.glob(llm_glob))

    if not configs:
        raise FileNotFoundError(f"No LLM configs found under {llm_path} with glob {llm_glob}")

    return [
        str(path.relative_to(PROJECT_ROOT))
        if path.is_absolute() and PROJECT_ROOT in path.parents
        else str(path)
        for path in configs
    ]


def get_model_name(config_path: str) -> str:
    return Path(config_path).stem


def normalize_result(
    raw_result: Any,
    instance: Dict[str, Any],
    dimension: str,
    subtype: str,
    authority_mode: str,
    target_llm_config: str,
    attacker_llm_config: str,
    judger_llm_config: str,
    family_path: Path,
    seed_path: Path,
    agent_scope: str
) -> Dict[str, Any]:
    if isinstance(raw_result, dict):
        result = dict(raw_result)
    else:
        result = {
            "raw_result": raw_result
        }

    if not result.get("instance_id") or result.get("instance_id") == "unknown_instance":
        result["instance_id"] = instance.get("instance_id")
    result.setdefault("dimension", dimension)
    result.setdefault("risk_dimension", dimension)
    result.setdefault("family_id", f"{dimension}.{subtype}")
    result.setdefault("risk_subtype", subtype)
    result.setdefault("authority_mode", authority_mode)
    result.setdefault("agent_scope", agent_scope)
    result.setdefault("data_scope", agent_scope)

    result["target_llm_config"] = target_llm_config
    result["target_model"] = get_model_name(target_llm_config)
    result["attacker_llm_config"] = attacker_llm_config
    result["judger_llm_config"] = judger_llm_config
    result["family_schema_path"] = str(family_path)
    result["seed_path"] = str(seed_path)

    judge = result.get("final_judge_result", {})
    if isinstance(judge, dict):
        if "final_label" not in result:
            result["final_label"] = judge.get("final_label") or judge.get("label")
        if "final_confidence" not in result:
            result["final_confidence"] = judge.get("confidence")

    return result


def run_one_case(
    runner_cls: Any,
    instance: Dict[str, Any],
    family_schema: Dict[str, Any],
    family_path: Path,
    seed_path: Path,
    agent_scope: str,
    dimension: str,
    subtype: str,
    authority_mode: str,
    target_llm_config: str,
    attacker_llm_config: str,
    judger_llm_config: str,
    max_turns: int,
    no_llm_attacker: bool
) -> Dict[str, Any]:
    runner_kwargs = {
        "dimension": dimension,
        "risk_dimension": dimension,
        "risk_subtype": subtype,
        "authority_mode": authority_mode,
        "target_llm_config": target_llm_config,
        "target_llm_config_path": target_llm_config,
        "attacker_llm_config": attacker_llm_config,
        "attacker_llm_config_path": attacker_llm_config,
        "judger_llm_config": judger_llm_config,
        "judger_llm_config_path": judger_llm_config,
        "family_schema": family_schema,
        "family_schema_path": str(family_path),
        "max_turns": max_turns,
        "no_llm_attacker": no_llm_attacker
    }

    runner = instantiate_runner(runner_cls, runner_kwargs)
    _, method = find_run_method(runner)

    method_kwargs = {
        "instance": instance,
        "scenario": instance,
        "task": instance,
        "family_schema": family_schema,
        "family_schema_path": str(family_path),
        "seed_path": str(seed_path),
        "dimension": dimension,
        "risk_dimension": dimension,
        "risk_subtype": subtype,
        "authority_mode": authority_mode,
        "target_llm_config": target_llm_config,
        "target_llm_config_path": target_llm_config,
        "attacker_llm_config": attacker_llm_config,
        "attacker_llm_config_path": attacker_llm_config,
        "judger_llm_config": judger_llm_config,
        "judger_llm_config_path": judger_llm_config,
        "max_turns": max_turns,
        "no_llm_attacker": no_llm_attacker
    }

    raw_result = call_runner_method(method, method_kwargs)

    return normalize_result(
        raw_result=raw_result,
        instance=instance,
        dimension=dimension,
        subtype=subtype,
        authority_mode=authority_mode,
        target_llm_config=target_llm_config,
        attacker_llm_config=attacker_llm_config,
        judger_llm_config=judger_llm_config,
        family_path=family_path,
        seed_path=seed_path
        ,
        agent_scope=agent_scope
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument("--dimension", type=str, default=DEFAULT_DIMENSION)
    parser.add_argument("--subtypes", nargs="+", default=["all"])
    parser.add_argument("--seed-filename", type=str, default="seeds.json")
    parser.add_argument(
        "--agent-scope",
        choices=["auto", "single_agent", "architecture_and_modules", "multi_agent_system", "external_environment", "interface_and_protocol"],
        default="auto",
        help="Data/output scope. auto resolves existing seed/family paths and writes under that scope."
    )

    parser.add_argument("--target-llm-config", type=str, default="configs/llm/gpt-4o-mini.yaml")
    parser.add_argument("--all-target-models", action="store_true")
    parser.add_argument("--llm-dir", type=str, default="configs/llm")
    parser.add_argument("--llm-glob", type=str, default="*.yaml")

    parser.add_argument("--attacker-llm-config", type=str, default="configs/llm/gpt-5.4.yaml")
    parser.add_argument("--judger-llm-config", type=str, default="configs/llm/gpt-5.4.yaml")

    parser.add_argument("--authority-modes", nargs="+", choices=["soft", "hard"], default=["soft"])
    parser.add_argument("--max-turns", type=int, default=4)
    parser.add_argument("--case-workers", type=int, default=1, help="Number of instances to run in parallel inside this eval process.")

    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start-index", type=int, default=0)

    parser.add_argument("--no-llm-attacker", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true", default=True, help=argparse.SUPPRESS)
    parser.add_argument("--fail-fast", action="store_true", help="Stop on the first failed case. Default: continue and record errors.")
    parser.add_argument("--skip-missing", action="store_true")

    parser.add_argument("--output-root", type=str, default="outputs/results")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--rerun-existing", action="store_true", help="Rerun cases even when successful results already exist.")

    args = parser.parse_args()
    if args.fail_fast:
        args.continue_on_error = False

    output_root = resolve_path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    subtypes = expand_subtypes(args.dimension, args.subtypes)
    target_model_configs = list_target_model_configs(
        all_target_models=args.all_target_models,
        target_llm_config=args.target_llm_config,
        llm_dir=args.llm_dir,
        llm_glob=args.llm_glob
    )

    run_config = {
        "dimension": args.dimension,
        "agent_scope": args.agent_scope,
        "seed_filename": args.seed_filename,
        "subtypes": subtypes,
        "target_model_configs": target_model_configs,
        "all_target_models": args.all_target_models,
        "attacker_llm_config": args.attacker_llm_config,
        "judger_llm_config": args.judger_llm_config,
        "authority_modes": args.authority_modes,
        "max_turns": args.max_turns,
        "case_workers": args.case_workers,
        "limit": args.limit,
        "start_index": args.start_index,
        "no_llm_attacker": args.no_llm_attacker,
        "continue_on_error": args.continue_on_error,
        "skip_missing": args.skip_missing,
        "resume": args.resume,
        "rerun_existing": args.rerun_existing,
        "output_root": str(output_root),
        "output_layout": "outputs/results/<single_agent|architecture_and_modules|multi_agent_system|external_environment|interface_and_protocol>/<dimension>/<subtype>/<model>/"
    }

    runner_cls = load_runner_class()

    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    completed_keys = set()

    if not args.rerun_existing:
        for subtype in subtypes:
            family_path = get_family_path(args.dimension, subtype, "single_agent" if args.agent_scope == "auto" else args.agent_scope)
            seed_path = get_seed_path(args.dimension, subtype, args.seed_filename, "single_agent" if args.agent_scope == "auto" else args.agent_scope)
            resolved_agent_scope = path_agent_scope(seed_path if seed_path.exists() else family_path)
            for target_llm_config in target_model_configs:
                model = get_model_name(target_llm_config)
                part_dir = partition_dir(output_root, resolved_agent_scope, args.dimension, subtype, model)
                existing_results_path = part_dir / "results.json"
                existing_errors_path = part_dir / "errors.json"

                if existing_results_path.exists():
                    existing_results = load_json(existing_results_path)
                    if isinstance(existing_results, list):
                        results.extend(item for item in existing_results if isinstance(item, dict))

                if args.resume and existing_errors_path.exists():
                    existing_errors = load_json(existing_errors_path)
                    if isinstance(existing_errors, list):
                        errors.extend(item for item in existing_errors if isinstance(item, dict))

        completed_keys = {
            case_key(item)
            for item in results + errors
            if isinstance(item, dict)
        }

        print(json.dumps({
            "skip_existing_results": True,
            "resume_errors": args.resume,
            "output_root": str(output_root),
            "loaded_results": len(results),
            "loaded_errors": len(errors),
            "completed_cases": len(completed_keys)
        }, ensure_ascii=False, indent=2))

    pending_cases: List[Dict[str, Any]] = []

    for subtype in subtypes:
        preferred_agent_scope = "single_agent" if args.agent_scope == "auto" else args.agent_scope
        family_path = get_family_path(args.dimension, subtype, preferred_agent_scope)
        seed_path = get_seed_path(args.dimension, subtype, args.seed_filename, preferred_agent_scope)
        resolved_agent_scope = path_agent_scope(seed_path if seed_path.exists() else family_path)

        if not family_path.exists() or not seed_path.exists():
            error = {
                "agent_scope": resolved_agent_scope,
                "subtype": subtype,
                "family_path": str(family_path),
                "seed_path": str(seed_path),
                "error": "missing_family_or_seed"
            }

            errors.append(error)

            if args.skip_missing or args.continue_on_error:
                print(json.dumps(error, ensure_ascii=False, indent=2))
                continue

            raise FileNotFoundError(error)

        family_schema = load_json(family_path)
        instances = load_instances(seed_path)

        if args.start_index:
            instances = instances[args.start_index:]

        if args.limit is not None:
            instances = instances[:args.limit]

        for target_llm_config in target_model_configs:
            for authority_mode in args.authority_modes:
                for instance_index, instance in enumerate(instances):
                    instance_id = instance.get("instance_id", f"{subtype}_{instance_index}")
                    current_key = case_key(
                        {},
                        fallback_subtype=subtype,
                        fallback_target_llm_config=target_llm_config,
                        fallback_authority_mode=authority_mode,
                        fallback_instance_id=instance_id
                    )

                    if current_key in completed_keys:
                        print(
                            f"\nSkipping completed: subtype={subtype}, "
                            f"model={get_model_name(target_llm_config)}, "
                            f"authority={authority_mode}, "
                            f"instance={instance_id}",
                            flush=True
                        )
                        continue

                    print(
                        f"\nQueued: subtype={subtype}, "
                        f"model={get_model_name(target_llm_config)}, "
                        f"authority={authority_mode}, "
                        f"instance={instance_id}",
                        flush=True
                    )

                    pending_cases.append({
                        "key": current_key,
                        "instance": instance,
                        "instance_id": instance_id,
                        "family_schema": family_schema,
                        "family_path": family_path,
                        "seed_path": seed_path,
                        "agent_scope": resolved_agent_scope,
                        "subtype": subtype,
                        "authority_mode": authority_mode,
                        "target_llm_config": target_llm_config,
                    })

    def execute_case(case: Dict[str, Any]) -> Dict[str, Any]:
        target_llm_config = case["target_llm_config"]
        subtype = case["subtype"]
        authority_mode = case["authority_mode"]
        instance_id = case["instance_id"]

        print(
            f"\nRunning: subtype={subtype}, "
            f"model={get_model_name(target_llm_config)}, "
            f"authority={authority_mode}, "
            f"instance={instance_id}",
            flush=True
        )

        try:
            result = run_one_case(
                runner_cls=runner_cls,
                instance=case["instance"],
                family_schema=case["family_schema"],
                family_path=case["family_path"],
                seed_path=case["seed_path"],
                agent_scope=case["agent_scope"],
                dimension=args.dimension,
                subtype=subtype,
                authority_mode=authority_mode,
                target_llm_config=target_llm_config,
                attacker_llm_config=args.attacker_llm_config,
                judger_llm_config=args.judger_llm_config,
                max_turns=args.max_turns,
                no_llm_attacker=args.no_llm_attacker
            )

            return {
                "status": "result",
                "key": case["key"],
                "result": result,
            }

        except Exception as e:
            return {
                "status": "error",
                "key": case["key"],
                "error": {
                    "dimension": args.dimension,
                    "agent_scope": case["agent_scope"],
                    "data_scope": case["agent_scope"],
                    "subtype": subtype,
                    "instance_id": instance_id,
                    "target_llm_config": target_llm_config,
                    "target_model": get_model_name(target_llm_config),
                    "authority_mode": authority_mode,
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }
            }

    case_workers = max(1, args.case_workers)

    if pending_cases:
        print(json.dumps({
            "queued_cases": len(pending_cases),
            "case_workers": case_workers
        }, ensure_ascii=False, indent=2))

    if case_workers == 1:
        for case in pending_cases:
            item = execute_case(case)

            if item["status"] == "result":
                results.append(item["result"])
                completed_keys.add(item["key"])
            else:
                error = item["error"]
                errors.append(error)
                completed_keys.add(item["key"])
                print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)

                if not args.continue_on_error:
                    write_partitioned_outputs(output_root, args.dimension, results, errors)
                    raise RuntimeError(error)

            write_partitioned_outputs(output_root, args.dimension, results, errors)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=case_workers) as executor:
            future_to_case = {
                executor.submit(execute_case, case): case
                for case in pending_cases
            }

            for future in concurrent.futures.as_completed(future_to_case):
                item = future.result()

                if item["status"] == "result":
                    results.append(item["result"])
                    completed_keys.add(item["key"])
                else:
                    error = item["error"]
                    errors.append(error)
                    completed_keys.add(item["key"])
                    print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)

                    if not args.continue_on_error:
                        write_partitioned_outputs(output_root, args.dimension, results, errors)
                        raise RuntimeError(error)

                write_partitioned_outputs(output_root, args.dimension, results, errors)

    write_partitioned_outputs(output_root, args.dimension, results, errors)

    for subtype in subtypes:
        preferred_agent_scope = "single_agent" if args.agent_scope == "auto" else args.agent_scope
        seed_path = get_seed_path(args.dimension, subtype, args.seed_filename, preferred_agent_scope)
        family_path = get_family_path(args.dimension, subtype, preferred_agent_scope)
        resolved_agent_scope = path_agent_scope(seed_path if seed_path.exists() else family_path)
        for target_llm_config in target_model_configs:
            model = get_model_name(target_llm_config)
            part_dir = partition_dir(output_root, resolved_agent_scope, args.dimension, subtype, model)
            part_config = {
                **run_config,
                "agent_scope": resolved_agent_scope,
                "risk_subtype": subtype,
                "target_llm_config": target_llm_config,
                "target_model": model,
                "results_json": str(part_dir / "results.json"),
                "errors_json": str(part_dir / "errors.json")
            }
            save_json(part_dir / "run_config.json", part_config)

    print(json.dumps({
        "dimension": args.dimension,
        "output_root": str(output_root),
        "num_results": len(results),
        "num_errors": len(errors),
        "partition_manifest_json": str(output_root / "partition_manifest.json"),
        "output_layout": str(output_root / "<single_agent|architecture_and_modules|multi_agent_system|external_environment|interface_and_protocol>" / args.dimension / "<subtype>" / "<model>")
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
