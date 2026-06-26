from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.tools.builder.dimension_tool_builder import build_tool_bundles_from_seed_file
from src.core.data_paths import list_subtypes, seed_path_for as resolve_seed_path


DEFAULT_DIMENSION_SUBTYPES = {
    "autonomy_authority_failure": [
        "unauthorized_decision",
        "privilege_escalation",
        "dangerous_action_execution",
        "single_agent_cascade",
    ],
    "goal_norm_misalignment": [
        "reward_hacking",
        "side_effect_negligence",
        "objective_drift",
    ],
    "interaction_understanding_failure": [
        "intent_misinterpretation",
        "sycophantic_compliance",
    ],
    "robustness_generalization_failure": [
        "adversarial_inducement_vulnerability",
        "long_horizon_task_instability",
        "misleading_context_vulnerability",
    ],
    "input_perception_risk": [
        "instruction_injection",
        "information_pollution",
    ],
    "memory_module_risk": [
        "memory_pollution",
        "context_hijacking",
        "summary_distortion",
    ],
    "reasoning_planning_risk": [
        "goal_decomposition_distortion",
        "constraint_omission",
        "risk_misassessment",
        "verification_failure",
    ],
    "action_tool_calling_risk": [
        "call_misjudgment",
        "permission_overreach",
        "tool_result_misuse",
        "system_brake_failure",
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
        "false_majority_signal",
    ],
}


def expand_subtypes(dimension: str, requested: List[str]) -> List[str]:
    if not requested or "all" in requested:
        if dimension in DEFAULT_DIMENSION_SUBTYPES:
            return DEFAULT_DIMENSION_SUBTYPES[dimension]

        discovered = list_subtypes(PROJECT_ROOT, dimension)
        if discovered:
            return discovered

        raise ValueError(f"No subtype list found for dimension: {dimension}")

    return requested


def seed_path_for(dimension: str, subtype: str) -> Path:
    return resolve_seed_path(PROJECT_ROOT, dimension, subtype)


def summarize_result(seed_path: Path, result: Dict[str, Any]) -> Dict[str, Any]:
    bundles = result.get("bundles", [])
    generated_count = sum(len(bundle.get("generated_tools", [])) for bundle in bundles)
    missing_specs_count = sum(len(bundle.get("missing_specs_before_generation", [])) for bundle in bundles)
    missing_impls_count = sum(len(bundle.get("missing_impls_before_generation", [])) for bundle in bundles)

    generated_tools = []
    missing_specs = []
    missing_impls = []

    for bundle in bundles:
        instance_id = bundle.get("instance_id", "")
        for item in bundle.get("generated_tools", []):
            generated_tools.append({
                "instance_id": instance_id,
                **item,
            })
        for name in bundle.get("missing_specs_before_generation", []):
            missing_specs.append({
                "instance_id": instance_id,
                "tool_name": name,
            })
        for name in bundle.get("missing_impls_before_generation", []):
            missing_impls.append({
                "instance_id": instance_id,
                "tool_name": name,
            })

    return {
        "seed_path": str(seed_path),
        "num_instances": result.get("num_instances", len(bundles)),
        "generated_count": generated_count,
        "missing_specs_count": missing_specs_count,
        "missing_impls_count": missing_impls_count,
        "generated_tools": generated_tools,
        "missing_specs_before_generation": missing_specs,
        "missing_impls_before_generation": missing_impls,
    }


def print_summary(summaries: List[Dict[str, Any]]) -> None:
    total_instances = sum(item["num_instances"] for item in summaries)
    total_generated = sum(item["generated_count"] for item in summaries)
    total_missing_specs = sum(item["missing_specs_count"] for item in summaries)
    total_missing_impls = sum(item["missing_impls_count"] for item in summaries)

    print("Tool build summary")
    print(f"- seed_files: {len(summaries)}")
    print(f"- instances: {total_instances}")
    print(f"- generated_tools: {total_generated}")
    print(f"- missing_specs_before_generation: {total_missing_specs}")
    print(f"- missing_impls_before_generation: {total_missing_impls}")

    print("\nPer seed file")
    for item in summaries:
        print(
            f"- {item['seed_path']}: "
            f"instances={item['num_instances']} "
            f"generated={item['generated_count']} "
            f"missing_specs={item['missing_specs_count']} "
            f"missing_impls={item['missing_impls_count']}"
        )

    generated = [
        tool
        for item in summaries
        for tool in item["generated_tools"]
    ]
    if generated:
        print("\nGenerated tools")
        for tool in generated:
            print(
                f"- {tool.get('instance_id')}: "
                f"{tool.get('tool_name')} "
                f"({tool.get('generated_part')}, role={tool.get('role')})"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dimension", required=True)
    parser.add_argument("--subtypes", nargs="*", default=["all"])
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if generation/precheck reports missing tools.")
    parser.add_argument("--summary-json", default=None, help="Optional path to write a machine-readable summary.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    subtypes = expand_subtypes(args.dimension, args.subtypes)
    summaries: List[Dict[str, Any]] = []

    for subtype in subtypes:
        seed_path = seed_path_for(args.dimension, subtype)
        if not seed_path.exists():
            raise FileNotFoundError(f"Seed file not found: {seed_path}")

        result = build_tool_bundles_from_seed_file(seed_path)
        summaries.append(summarize_result(seed_path, result))

    print_summary(summaries)

    if args.summary_json:
        summary_path = Path(args.summary_json)
        if not summary_path.is_absolute():
            summary_path = PROJECT_ROOT / summary_path
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps({
                "dimension": args.dimension,
                "subtypes": subtypes,
                "summaries": summaries,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nWrote summary JSON: {summary_path}")

    if args.strict:
        missing_total = sum(
            item["missing_specs_count"] + item["missing_impls_count"]
            for item in summaries
        )
        if missing_total:
            sys.exit(1)


if __name__ == "__main__":
    main()
