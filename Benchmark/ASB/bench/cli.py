"""Command line entry for smoke-testing the lightweight benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .adapters import MockAgentAdapter
from Benchmark.mcp_safety import (
    MCPSafetyBenchmarkRunner,
    MockMCPTraceAgentAdapter,
    mcp_result_to_dict,
    summarize_mcp_results,
)
from .runner import BenchmarkRunner, result_to_dict, summarize_results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Run examples with MockAgentAdapter.")
    parser.add_argument(
        "--mcp-demo",
        action="store_true",
        help="Run examples with simulated MCP-SafetyBench taxonomy and trace evaluators.",
    )
    parser.add_argument("--tasks", default="examples/tasks.jsonl")
    parser.add_argument("--normal-tools", default="examples/normal_tools.jsonl")
    parser.add_argument("--attack-tools", default="examples/attack_tools.jsonl")
    parser.add_argument("--channels", default="dpi,opi,mp,pot")
    parser.add_argument(
        "--attack-types",
        default="naive,fake_completion,escape_characters,context_ignoring,combined_attack",
    )
    parser.add_argument(
        "--mcp-categories",
        default=(
            "Tool Poisoning-Tool Redirection,Function Return Injection,"
            "Data Tampering,Intent Injection,Replay Injection,Rug Pull Attack"
        ),
    )
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    if not args.demo and not args.mcp_demo:
        raise SystemExit("Use --demo or --mcp-demo for a built-in mock run, or import this package.")

    if args.mcp_demo:
        runner = MCPSafetyBenchmarkRunner.from_jsonl(
            tasks_path=args.tasks,
            normal_tools_path=args.normal_tools,
            attack_tools_path=args.attack_tools,
        )
        results = runner.run(
            adapter=MockMCPTraceAgentAdapter(),
            categories=[x.strip() for x in args.mcp_categories.split(",") if x.strip()],
        )
        payload = {
            "summary": summarize_mcp_results(results),
            "results": [mcp_result_to_dict(result) for result in results],
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
        else:
            print(text)
        return

    runner = BenchmarkRunner.from_jsonl(
        tasks_path=args.tasks,
        normal_tools_path=args.normal_tools,
        attack_tools_path=args.attack_tools,
    )
    results = runner.run(
        adapter=MockAgentAdapter(),
        attack_channels=[x.strip() for x in args.channels.split(",") if x.strip()],
        attack_types=[x.strip() for x in args.attack_types.split(",") if x.strip()],
    )

    payload = {
        "summary": summarize_results(results),
        "results": [result_to_dict(result) for result in results],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
