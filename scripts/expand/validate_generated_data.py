#!/usr/bin/env python3
"""
Validate generated seed data before promoting it into a task seed file.

This script combines:
- generic and dimension-specific generated-data validation from expand_dimension_data.py
- tool-bundle construction and target-visible tool-spec visibility checks

It accepts arbitrary generated JSON files rather than only canonical
data/single_agent/tasks/<dimension>/<subtype>_seeds/seeds.json paths.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.expand.expand_dimension_data import (  # noqa: E402
    resolve_path,
    validate_generated_data,
)


FORBIDDEN_VISIBLE_TERMS = [
    "intent_misread_action",
    "risky action",
    "risky_path",
    "unsafe",
    "unsafe_action",
    "misread",
    "intent_misinterpretation",
    "risk behavior",
    "risk path",
    "hidden",
    "hidden_risk",
    "hidden_execution",
    "judge",
    "judge_spec",
    "boundary_basis",
    "expected_risk_points",
    "reward_hacking",
    "side_effect",
    "objective_drift",
    "sycophancy",
    "injection",
    "attack",
    "dangerous_action",
    "target risk",
    "failure path",
]

INTERNAL_ROLE_TERMS = [
    "observation",
    "safe_action",
    "risky_action",
    "unsafe_action",
    "intent_misread_action",
    "reporting_action",
    "metric_affecting_action",
    "readiness_publication",
    "privilege_boundary_crossing",
    "dangerous_action",
]


def infer_id(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        raw = value.get("id")
        return str(raw) if raw is not None else None
    if isinstance(value, str):
        return value
    return None


def infer_dimension_and_subtype(seed_data: Any) -> tuple[Optional[str], Optional[str]]:
    if not isinstance(seed_data, dict):
        return None, None

    family_id = seed_data.get("family_id")
    dimension = infer_id(seed_data.get("risk_dimension"))
    subtype = infer_id(seed_data.get("risk_subtype"))

    if isinstance(family_id, str) and "." in family_id:
        family_dimension, family_subtype = family_id.split(".", 1)
        dimension = dimension or family_dimension
        subtype = subtype or family_subtype

    return dimension, subtype


def save_json(path: str | Path, data: Any) -> None:
    path = resolve_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_seed(seed_path: str | Path) -> tuple[Any, List[Dict[str, Any]]]:
    path = resolve_path(seed_path)
    with path.open("r", encoding="utf-8") as f:
        seed_data = json.load(f)

    if isinstance(seed_data, list):
        instances = seed_data
    elif isinstance(seed_data, dict) and isinstance(seed_data.get("instances"), list):
        instances = seed_data["instances"]
    elif isinstance(seed_data, dict) and isinstance(seed_data.get("tasks"), list):
        instances = seed_data["tasks"]
    elif isinstance(seed_data, dict):
        instances = [seed_data]
    else:
        raise ValueError(f"Seed file must contain a JSON object or list: {path}")

    inherited_fields = {
        key: seed_data.get(key)
        for key in ["family_id", "risk_dimension", "risk_subtype"]
        if isinstance(seed_data, dict) and seed_data.get(key) is not None
    }

    normalized_instances: List[Dict[str, Any]] = []
    for instance in instances:
        if not isinstance(instance, dict):
            raise ValueError("Each seed instance must be a JSON object.")
        enriched = dict(inherited_fields)
        enriched.update(instance)
        normalized_instances.append(enriched)

    return seed_data, normalized_instances


def build_tool_bundle(instance: Dict[str, Any], config_path: Optional[str] = None) -> Dict[str, Any]:
    try:
        from src.tools.builder.dimension_tool_builder import build_tool_bundle_for_instance
    except ImportError as exc:
        raise RuntimeError(
            "Cannot import src.tools.builder.dimension_tool_builder.build_tool_bundle_for_instance."
        ) from exc

    return build_tool_bundle_for_instance(instance, config_path=config_path)


def visible_description(tool_spec: Dict[str, Any]) -> str:
    return (
        tool_spec.get("target_visible_description")
        or tool_spec.get("description")
        or tool_spec.get("capability")
        or ""
    )


def find_terms(text: str, terms: List[str]) -> List[str]:
    lower_text = text.lower()
    found: List[str] = []
    for term in terms:
        pattern = r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])"
        if re.search(pattern, lower_text):
            found.append(term)
    return found


def check_visible_tool_fields(tool_spec: Dict[str, Any]) -> Dict[str, Any]:
    tool_name = str(tool_spec.get("tool_name", ""))
    description = str(visible_description(tool_spec))
    parameters = tool_spec.get("parameters", {})
    parameters_text = json.dumps(parameters, ensure_ascii=False, sort_keys=True)

    fields = {
        "tool_name": tool_name,
        "visible_description": description,
        "parameters": parameters_text,
    }
    issues: List[Dict[str, str]] = []

    for field, value in fields.items():
        for term in find_terms(value, FORBIDDEN_VISIBLE_TERMS):
            issues.append({
                "field": field,
                "type": "forbidden_term",
                "evidence": term,
                "explanation": "Target-visible field contains a forbidden risk, judge, or internal-framework term.",
            })
        for term in find_terms(value, INTERNAL_ROLE_TERMS):
            issues.append({
                "field": field,
                "type": "internal_role_leak",
                "evidence": term,
                "explanation": "Target-visible field contains an internal tool role name.",
            })

    deduped: List[Dict[str, str]] = []
    seen = set()
    for issue in issues:
        key = (issue["field"], issue["type"], issue["evidence"])
        if key not in seen:
            seen.add(key)
            deduped.append(issue)

    suggestion = description.strip()
    if suggestion:
        suggestion = suggestion[0].upper() + suggestion[1:]
        if not suggestion.endswith("."):
            suggestion += "."

    return {
        "tool_name": tool_name,
        "visible_description": description,
        "parameters": parameters,
        "status": "fail" if deduped else "pass",
        "issues": deduped,
        "suggested_target_visible_description": suggestion if deduped else None,
    }


def check_bundles(
    *,
    seed_path: str,
    bundles: List[Dict[str, Any]],
) -> Dict[str, Any]:
    tool_reports: List[Dict[str, Any]] = []
    for bundle in bundles:
        instance_id = str(bundle.get("instance_id", ""))
        for tool_spec in bundle.get("tool_specs", []):
            if not isinstance(tool_spec, dict):
                continue
            report = check_visible_tool_fields(tool_spec)
            report["instance_id"] = instance_id
            tool_reports.append(report)

    return {
        "seed_path": str(resolve_path(seed_path)),
        "total_tools": len(tool_reports),
        "problem_count": sum(1 for item in tool_reports if item.get("status") != "pass"),
        "tools": tool_reports,
    }


def validate_top_level(
    seed_data: Any,
    *,
    expected_count: Optional[int],
    require_no_generation_metadata: bool,
) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []

    if not isinstance(seed_data, dict):
        issues.append({
            "severity": "error",
            "message": "Generated data must be a JSON object with an instances list.",
        })
        return issues

    instances = seed_data.get("instances")
    if not isinstance(instances, list):
        issues.append({
            "severity": "error",
            "message": "Generated data must contain an instances list.",
        })
    elif expected_count is not None and len(instances) != expected_count:
        issues.append({
            "severity": "error",
            "message": f"Expected {expected_count} instances, found {len(instances)}.",
        })

    if require_no_generation_metadata and "generation_metadata" in seed_data:
        issues.append({
            "severity": "error",
            "message": "Top-level generation_metadata must be omitted from promoted generated data.",
        })

    return issues


def run_schema_validation(
    seed_data: Any,
    *,
    dimension: str,
    subtype: str,
) -> List[Dict[str, str]]:
    try:
        validate_generated_data(seed_data, dimension=dimension, subtype=subtype)
    except Exception as exc:
        return [
            {
                "severity": "error",
                "message": line,
            }
            for line in str(exc).splitlines()
            if line.strip()
        ]
    return []


def run_tool_visibility_validation(
    *,
    seed_path: str,
    config_path: Optional[str],
) -> Dict[str, Any]:
    _, instances = load_seed(seed_path)
    bundles = [
        build_tool_bundle(instance, config_path=config_path)
        for instance in instances
    ]
    return check_bundles(
        seed_path=seed_path,
        bundles=bundles,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-path", required=True, help="Generated seed JSON to validate, e.g. generation.json.")
    parser.add_argument("--dimension", default=None, help="Risk dimension id. Inferred from the file when omitted.")
    parser.add_argument("--subtype", default=None, help="Risk subtype id. Inferred from the file when omitted.")
    parser.add_argument("--expected-count", type=int, default=None, help="Require exactly this many instances.")
    parser.add_argument(
        "--allow-generation-metadata",
        action="store_true",
        help="Allow top-level generation_metadata. By default it is treated as an error.",
    )
    parser.add_argument(
        "--skip-tool-visibility",
        action="store_true",
        help="Only run generated-data schema/dimension validation.",
    )
    parser.add_argument("--tool-config-path", default=None)
    parser.add_argument(
        "--strict-tool-visibility",
        action="store_true",
        help="Count target-visible tool-spec visibility problems as strict validation errors.",
    )
    parser.add_argument(
        "--include-passing-tools",
        action="store_true",
        help="Include passing tool visibility rows in the JSON report. By default only problem tools are listed.",
    )
    parser.add_argument("--output-report", default=None)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if any error is found.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    seed_path = resolve_path(args.seed_path)

    with seed_path.open("r", encoding="utf-8") as f:
        seed_data = json.load(f)

    inferred_dimension, inferred_subtype = infer_dimension_and_subtype(seed_data)
    dimension = args.dimension or inferred_dimension
    subtype = args.subtype or inferred_subtype
    if not dimension or not subtype:
        raise ValueError("Could not infer --dimension and --subtype from the generated file.")

    top_level_issues = validate_top_level(
        seed_data,
        expected_count=args.expected_count,
        require_no_generation_metadata=not args.allow_generation_metadata,
    )
    schema_issues = run_schema_validation(
        seed_data,
        dimension=dimension,
        subtype=subtype,
    )

    tool_report: Optional[Dict[str, Any]] = None
    tool_visibility_error: Optional[str] = None
    if not args.skip_tool_visibility:
        try:
            tool_report = run_tool_visibility_validation(
                seed_path=str(seed_path),
                config_path=args.tool_config_path,
            )
        except Exception as exc:
            tool_visibility_error = str(exc)

    structural_error_count = sum(
        1
        for item in top_level_issues + schema_issues
        if item.get("severity") == "error"
    )
    tool_problem_count = (tool_report or {}).get("problem_count", 0)
    tool_error_count = tool_problem_count if args.strict_tool_visibility else 0
    if tool_visibility_error:
        tool_error_count += 1
    error_count = structural_error_count + tool_error_count

    report: Dict[str, Any] = {
        "seed_path": str(seed_path),
        "dimension": dimension,
        "subtype": subtype,
        "instances": len(seed_data.get("instances", [])) if isinstance(seed_data, dict) else None,
        "expected_count": args.expected_count,
        "top_level_issues": top_level_issues,
        "schema_issues": schema_issues,
        "tool_visibility": {
            "skipped": args.skip_tool_visibility,
            "strict": args.strict_tool_visibility,
            "problem_count": tool_problem_count,
            "total_tools": (tool_report or {}).get("total_tools"),
            "error": tool_visibility_error,
        },
        "status": "pass" if error_count == 0 else "fail",
        "error_count": error_count,
        "structural_error_count": structural_error_count,
    }

    if tool_report is not None:
        tools = tool_report.get("tools", [])
        if not args.include_passing_tools:
            tools = [item for item in tools if item.get("status") != "pass"]
        report["tool_visibility"]["tools"] = tools

    if args.output_report:
        save_json(args.output_report, report)

    stdout_report = {
        key: value
        for key, value in report.items()
        if key != "tool_visibility"
    }
    stdout_report["tool_visibility"] = {
        key: value
        for key, value in report["tool_visibility"].items()
        if key != "tools"
    }
    if args.output_report:
        stdout_report["output_report"] = str(resolve_path(args.output_report))

    print(json.dumps(stdout_report, ensure_ascii=False, indent=2))

    if args.strict and error_count:
        sys.exit(1)


if __name__ == "__main__":
    main()
