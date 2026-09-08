from __future__ import annotations

import unittest
from pathlib import Path

from scripts.asb_import.case_builder import build_asb_cases
from scripts.asb_import.loaders import load_attack_tools, load_normal_tools, load_tasks


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = PROJECT_ROOT / "scripts" / "test" / "fixtures" / "asb"
SOURCE_ROOT = PROJECT_ROOT / "data" / "source_benchmarks" / "asb"


class ASBImportTests(unittest.TestCase):
    def test_full_source_snapshot_counts(self) -> None:
        self.assertEqual(len(load_tasks(SOURCE_ROOT / "tasks.jsonl")), 51)
        self.assertEqual(len(load_normal_tools(SOURCE_ROOT / "normal_tools.jsonl")), 20)
        self.assertEqual(len(load_attack_tools(SOURCE_ROOT / "attack_tools.jsonl")), 400)

    def test_fixture_case_matrix(self) -> None:
        cases = build_asb_cases(
            tasks=load_tasks(FIXTURE_ROOT / "tasks.jsonl"),
            normal_tools=load_normal_tools(FIXTURE_ROOT / "normal_tools.jsonl"),
            attack_tools=load_attack_tools(FIXTURE_ROOT / "attack_tools.jsonl"),
        )

        self.assertEqual(len(cases), 40)
        self.assertEqual(
            {case.attack_channel for case in cases}, {"dpi", "opi", "mp", "pot"}
        )
        self.assertEqual(
            {case.attack_type for case in cases},
            {
                "naive",
                "fake_completion",
                "escape_characters",
                "context_ignoring",
                "combined_attack",
            },
        )

    def test_each_channel_uses_its_expected_injection_point(self) -> None:
        cases = build_asb_cases(
            tasks=load_tasks(FIXTURE_ROOT / "tasks.jsonl")[:1],
            normal_tools=load_normal_tools(FIXTURE_ROOT / "normal_tools.jsonl"),
            attack_tools=load_attack_tools(FIXTURE_ROOT / "attack_tools.jsonl")[:1],
            attack_channels=("dpi", "opi", "mp", "pot"),
            attack_types=("naive",),
        )
        by_channel = {case.attack_channel: case for case in cases}

        self.assertEqual(by_channel["dpi"].metadata["injection_point"], "user_prompt")
        self.assertEqual(
            by_channel["opi"].metadata["injection_point"], "tool_observation"
        )
        self.assertEqual(by_channel["mp"].metadata["injection_point"], "memory")
        self.assertEqual(by_channel["pot"].metadata["injection_point"], "planner_prompt")
        self.assertIsNotNone(by_channel["opi"].observation_suffix)
        self.assertIsNotNone(by_channel["mp"].memory_context)
        self.assertIsNotNone(by_channel["pot"].planner_context)


if __name__ == "__main__":
    unittest.main()
