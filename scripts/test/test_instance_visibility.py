from __future__ import annotations

from copy import deepcopy
import importlib
from functools import lru_cache
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import yaml

from scripts.run.run_dimension_eval import load_instances
from src.core.instance_adapter import normalize_instance
from src.targets.single_agent_safety_prompt_builder import SingleAgentSafetyPromptBuilder
from src.targets.llm_target import LLMTarget
from src.targets.visibility import PRIVATE_KEYS, visible_tool_names
from src.tools.builder.dimension_tool_builder import infer_tool_config_path


ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=None)
def tool_config(path):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def seeds():
    for scope in ("single_agent", "architecture_and_modules", "multi_agent_system",
                  "external_environment", "interface_and_protocol"):
        for path in (ROOT / "data" / scope / "tasks").rglob("seeds.json"):
            raw = json.loads(path.read_text(encoding="utf-8"))
            for instance in raw["instances"]:
                yield path, instance


def bundle_for(instance):
    # Enough for prompt/parser tests without invoking spec generation or model APIs.
    roles = instance["tool_manifest"]["required_tool_roles"]
    config = tool_config(str(infer_tool_config_path(instance)))
    specs = [{"tool_name": name,
              "description": role.get("description", role.get("capability", "Operation")),
              "parameters": {"type": "object", "properties": {}}}
             for role in roles
             for name in ([role["preferred_tool_name"]] if role.get("preferred_tool_name")
                          else config.get("role_mapping", {}).get(role["role"], []))]
    specs = list({spec["tool_name"]: spec for spec in specs}.values())
    return {"tool_specs": specs, "tool_names": [spec["tool_name"] for spec in specs]}


class InstanceVisibilityTests(unittest.TestCase):
    def test_all_seeds_have_tasks_and_no_private_fields(self):
        count = 0
        builder = SingleAgentSafetyPromptBuilder()
        def check(value):
            if isinstance(value, dict):
                self.assertFalse(set(value) & PRIVATE_KEYS)
                self.assertFalse(any(key.startswith("hidden_") for key in value))
                for item in value.values():
                    check(item)
            elif isinstance(value, list):
                for item in value:
                    check(item)
        for path, raw in seeds():
            with self.subTest(path=str(path), id=raw.get("id", raw.get("instance_id"))):
                instance = normalize_instance(raw)
                bundle = bundle_for(instance)
                for mode in ("soft", "hard"):
                    messages = builder.build_messages(raw, bundle, authority_mode=mode)
                    payload = json.loads(messages[1]["content"].split("\n", 1)[1])
                    self.assertTrue(payload.get("task_context"))
                    self.assertTrue(payload.get("visible_environment_state"))
                    self.assertTrue(payload.get("available_tools"))
                    check(payload)
                count += 1
        self.assertEqual(count, 497)

    def test_56_legacy_instances_preserve_source_and_judge_evidence(self):
        count = 0
        for path, raw in seeds():
            if "instruction" not in raw:
                continue
            original = deepcopy(raw)
            instance = normalize_instance(raw)
            self.assertEqual(raw, original)
            self.assertEqual(normalize_instance(instance), instance)
            self.assertEqual(instance["instance_id"], raw["id"])
            self.assertEqual(instance["judge_spec"]["hidden_reference"]["source_environment"], raw["environment"])
            self.assertEqual(instance["attacker"]["objective"], raw["environment"]["attacker_goal_original"])
            self.assertNotEqual(instance["attacker"]["objective"], raw["environment"]["attack_goal"])
            self.assertIn(instance["instance_id"], [item["instance_id"] for item in load_instances(path)])
            visible_names = visible_tool_names(bundle_for(instance)["tool_specs"]).values()
            for name in visible_names:
                for label in ("misjudged", "permission_overreach", "misuse_tool_result",
                              "skip_system_brake", "distort_plan_decomposition",
                              "omit_planning_constraints", "misassess_plan_risk", "skip_plan_verification"):
                    self.assertNotIn(label, name)
            if raw["source"] == "ASB_POT":
                text = SingleAgentSafetyPromptBuilder().build_messages(raw, bundle_for(instance))[1]["content"]
                self.assertIn(raw["environment"]["pot_trigger"], text)
                self.assertIn("planning_examples", text)
                self.assertNotIn("Poisoned plan-of-thought", text)
            count += 1
        self.assertEqual(count, 56)

    def test_aliases_round_trip_for_all_seeds(self):
        target = LLMTarget.__new__(LLMTarget)
        for _, raw in seeds():
            bundle = bundle_for(raw)
            aliases = visible_tool_names(bundle["tool_specs"])
            self.assertEqual(len(set(aliases.values())), len(aliases))
            for internal, visible in aliases.items():
                response = target._normalize_response(
                    {"response_type": "tool_call", "tool_name": visible, "arguments": {}}, "", bundle)
                self.assertEqual(response["tool_name"], internal)

    def test_checkpoint_facts_and_scenario_survive(self):
        builder = SingleAgentSafetyPromptBuilder()
        for path, raw in seeds():
            if path.parts[-5] not in {"external_environment", "interface_and_protocol"}:
                continue
            payload = json.loads(builder.build_messages(raw, bundle_for(raw))[1]["content"].split("\n", 1)[1])
            visible = payload["visible_environment_state"]
            self.assertEqual(visible["reported_condition"], raw["environment_state"]["attack_or_failure_trigger"])
            for key in ("source_registry", "authoritative_state", "authorization_context", "protocol_trace"):
                if key in raw["environment_state"]:
                    self.assertEqual(visible[key], raw["environment_state"][key])
            self.assertNotIn("despite the unresolved", payload["operational_consequence"])

    def test_observations_hide_verdict_but_preserve_evidence_and_alias(self):
        builder = SingleAgentSafetyPromptBuilder()
        bundle = {"tool_specs": [{"tool_name": "systemmonitor_misjudged_call"}]}
        messages = builder.build_messages(
            {"target_spec": {"task_context": "Review monitoring"}}, bundle,
            tool_observations=[{"tool_name": "systemmonitor_misjudged_call", "risk_event": "private",
                "observation": {"call_misjudgment_detected": True, "authorization_present": False,
                                "signature_verified": False, "hidden_reference": "private"}}])
        observation = json.loads(messages[-1]["content"].split("\n", 1)[1])
        self.assertEqual(observation, {"tool_name": "systemmonitor_selected_call", "observation": {
            "authorization_present": False, "signature_verified": False}})

    def test_runner_adapts_direct_legacy_call_and_executes_tool(self):
        from src.runners.dimension_runner import DimensionRunner
        raw = next(raw for _, raw in seeds() if raw.get("source") == "ASB_ACTION_TOOL_CALLING")
        bundle = bundle_for(raw)
        bundle.update(tool_impl_module="src.tools.impl.action_tool_calling_risk_tools",
                      tool_impl_class="ActionToolCallingRiskTools")
        tool_name = raw["tool_manifest"]["forbidden_tools"][0]
        with patch("src.runners.dimension_runner.build_tool_bundle_for_instance", return_value=bundle) as build, \
             patch("src.targets.llm_target.LLMTarget._call_llm", return_value=json.dumps({
                 "response_type": "tool_call", "tool_name": visible_tool_names(bundle["tool_specs"])[tool_name], "arguments": {}})), \
             patch("src.judgers.dispatcher.JudgerDispatcher.judge", return_value={"label": "unsafe"}) as judge:
            result = DimensionRunner(max_turns=1, no_llm_attacker=True).run_instance(raw)
        self.assertEqual(build.call_args.args[0]["instance_id"], raw["id"])
        self.assertTrue(result["runtime_state"]["forbidden_tool_called"])
        self.assertEqual(result["executed_tool_names"], [tool_name])
        self.assertTrue(judge.call_args.kwargs["instance"]["judge_spec"])

    def test_all_legacy_tool_registries_execute_and_judge_receives_reference(self):
        from src.judgers.dimension_llm_judger import DimensionLLMJudger
        from src.attackers.dimension_attacker import DimensionAttacker
        for _, raw in seeds():
            if "instruction" not in raw:
                continue
            instance = normalize_instance(raw)
            config = tool_config(str(infer_tool_config_path(instance)))
            cls = getattr(importlib.import_module(config["tool_impl_module"]), config["tool_impl_class"])
            registry = cls(instance).get_tool_registry()
            for role in instance["tool_manifest"]["required_tool_roles"]:
                name = role["preferred_tool_name"]
                self.assertIn(name, registry)
                env = cls(instance)
                env.call_tool(name, {})
                self.assertEqual(env.get_runtime_state()["forbidden_tool_called"], role["role"] != "normal_task_tool")
            attacker = DimensionAttacker.__new__(DimensionAttacker)
            self.assertEqual(attacker.next_message(raw, turn_count=0)["content"], raw["environment"]["attacker_instruction"])
            with patch.object(DimensionLLMJudger, "_call_llm", return_value='{"label":"safe"}') as call:
                judge = DimensionLLMJudger()
                judge.judge(raw)
            self.assertIn(raw["environment"]["original_task"], call.call_args.args[0])
            self.assertIn("hidden_reference", call.call_args.args[0])

    def test_alias_collision_is_deterministic(self):
        specs = [{"tool_name": "selected_action"}, {"tool_name": "unsafe_action"},
                 {"tool_name": "another", "target_visible_name": "selected_action"}]
        self.assertEqual(list(visible_tool_names(specs).values()),
                         ["selected_action", "selected_action_2", "selected_action_3"])


if __name__ == "__main__":
    unittest.main()
