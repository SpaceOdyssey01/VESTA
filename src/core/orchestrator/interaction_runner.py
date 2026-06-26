from typing import Any, Dict, List, Optional

from src.core.tool.spec_schema import ToolSpecFile

class InteractionRunner:
    def __init__(self, attacker, target_runner, judger=None):
        self.attacker = attacker
        self.target_runner = target_runner
        self.judger = judger

    def run_once(self, risk_dimension: str, tool_specs=None, context=None):
        scenario = self.attacker.build_scenario(
            risk_dimension=risk_dimension,
            tool_specs=tool_specs or [],
            context=context
        )

        return {
            "scenario": {
                "scenario_id": scenario.scenario_id,
                "risk_dimension": scenario.risk_dimension,
                "attacker_goal": scenario.attacker_goal,
                "instruction": scenario.instruction,
                "observation": scenario.observation,
                "hidden_state": scenario.hidden_state,
                "allowed_tools": scenario.allowed_tools,
                "expected_risk_points": scenario.expected_risk_points,
                "metadata": scenario.metadata,
            }
        }

    def _tool_spec_to_dict(self, spec: ToolSpecFile) -> Dict[str, Any]:
        return {
            "tool_name": spec.tool_name,
            "description": spec.description,
            "category": spec.category,
            "tool_type": spec.tool_type,
            "tool_mode": spec.tool_mode,
            "risk_level": spec.risk_level,
            "requires_confirmation": spec.requires_confirmation,
            "input_schema": spec.input_schema,
            "required_parameters": spec.required_parameters,
            "output_schema": spec.output_schema,
            "possible_risk_dimensions": spec.possible_risk_dimensions,
            "tags": spec.tags,
        }

    def _scenario_to_dict(self, scenario) -> Dict[str, Any]:
        return {
            "scenario_id": scenario.scenario_id,
            "risk_dimension": scenario.risk_dimension,
            "attacker_goal": scenario.attacker_goal,
            "instruction": scenario.instruction,
            "observation": scenario.observation,
            "hidden_state": scenario.hidden_state,
            "allowed_tools": scenario.allowed_tools,
            "expected_risk_points": scenario.expected_risk_points,
            "attack_turns": [
                {
                    "turn_id": t.turn_id,
                    "attacker_message": t.attacker_message
                }
                for t in scenario.attack_turns
            ],
            "metadata": scenario.metadata,
        }
