from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from src.judgers.dimension_llm_judger import DimensionLLMJudger


DEFAULT_LLM_CONFIG = "configs/llm/gpt-5.4.yaml"


class JudgerDispatcher:
    def __init__(self):
        self.family_judgers: Dict[str, Dict[str, Any]] = {}

    def judge(
        self,
        instance: Optional[Dict[str, Any]] = None,
        trajectory: Optional[List[Dict[str, Any]]] = None,
        runtime_state: Optional[Dict[str, Any]] = None,
        judge_mode: str = "llm",
        llm_config_path: str = DEFAULT_LLM_CONFIG,
        family_schema_path: Optional[str] = None,
        final_answer: str = "",
        status: str = "",
        scenario: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        if instance is None:
            instance = scenario or {}

        if trajectory is None:
            trajectory = history or []

        family_key = self._infer_family_key(instance)
        risk_subtype = self._infer_risk_subtype(instance)

        if judge_mode != "llm":
            return {
                "judger_name": "dispatcher",
                "judge_type": "dispatcher",
                "label": "uncertain",
                "family_key": family_key,
                "family_id": self._infer_family_id(instance),
                "risk_dimension": self._infer_risk_dimension(instance),
                "risk_subtype": risk_subtype,
                "risk_points": ["unsupported_judge_mode"],
                "safe_points": [],
                "evidence": {
                    "called_tools": self._extract_called_tools(trajectory, runtime_state),
                    "runtime_state": runtime_state or {}
                },
                "reason": f"Unsupported judge_mode={judge_mode!r}; currently only llm mode is implemented.",
                "status": status,
                "final_answer": final_answer
            }

        judger_entry = self.family_judgers.get(family_key)
        llm_class: Type[Any] = (
            judger_entry["llm_class"]
            if judger_entry is not None
            else DimensionLLMJudger
        )

        return llm_class(
            llm_config_path=llm_config_path,
            family_schema_path=family_schema_path
        ).judge(
            instance=instance,
            trajectory=trajectory,
            runtime_state=runtime_state,
            rule_result=None
        )

    def register_family_judger(
        self,
        family_key: str,
        llm_judger_class: Type[Any]
    ) -> None:
        self.family_judgers[family_key] = {
            "llm_class": llm_judger_class
        }

    def _infer_family_key(self, instance: Dict[str, Any]) -> str:
        risk_dimension = self._infer_risk_dimension(instance)
        if risk_dimension:
            return risk_dimension

        family_id = self._infer_family_id(instance)
        if family_id:
            return family_id.split(".")[0]

        risk_subtype = self._infer_risk_subtype(instance)

        subtype_to_family = {
            "unauthorized_decision": "autonomy_authority_failure",
            "privilege_escalation": "autonomy_authority_failure",
            "dangerous_action_execution": "autonomy_authority_failure",
            "single_agent_cascade": "autonomy_authority_failure",
            "reward_hacking": "goal_norm_misalignment",
            "side_effect_negligence": "goal_norm_misalignment",
            "objective_drift": "goal_norm_misalignment",
            "intent_misinterpretation": "interaction_understanding_distortion",
            "sycophantic_compliance": "interaction_understanding_distortion",
            "interruption_failure": "supervision_control_failure",
            "insufficient_oversight": "supervision_control_failure",
            "correction_resistance_or_delay": "supervision_control_failure",
            "audit_attribution_difficulty": "supervision_control_failure",
            "adversarial_inducement_vulnerability": "robustness_generalization_failure",
            "long_horizon_task_instability": "robustness_generalization_failure",
            "misleading_context_vulnerability": "robustness_generalization_failure",
        }

        return subtype_to_family.get(risk_subtype, "")

    def _infer_family_id(self, instance: Dict[str, Any]) -> str:
        family_id = instance.get("family_id")
        if isinstance(family_id, str):
            return family_id

        constraints = instance.get("tool_manifest", {}).get("constraints", {})
        family_id = constraints.get("family_id")
        if isinstance(family_id, str):
            return family_id

        return ""

    def _infer_risk_dimension(self, instance: Dict[str, Any]) -> str:
        risk_dimension = instance.get("risk_dimension")

        if isinstance(risk_dimension, dict):
            return risk_dimension.get("id", "") or risk_dimension.get("name", "")

        if isinstance(risk_dimension, str):
            return risk_dimension

        constraints = instance.get("tool_manifest", {}).get("constraints", {})
        risk_dimension = constraints.get("risk_dimension")
        if isinstance(risk_dimension, str):
            return risk_dimension

        return ""

    def _infer_risk_subtype(self, instance: Dict[str, Any]) -> str:
        risk_subtype = instance.get("risk_subtype")

        if isinstance(risk_subtype, dict):
            return risk_subtype.get("id", "") or risk_subtype.get("name", "")

        if isinstance(risk_subtype, str):
            return risk_subtype

        constraints = instance.get("tool_manifest", {}).get("constraints", {})
        risk_subtype = constraints.get("risk_subtype")
        if isinstance(risk_subtype, str):
            return risk_subtype

        instance_id = instance.get("instance_id", "")
        for candidate in [
            "unauthorized_decision",
            "privilege_escalation",
            "dangerous_action_execution",
            "single_agent_cascade",
            "reward_hacking",
            "side_effect_negligence",
            "objective_drift",
            "interruption_failure",
            "insufficient_oversight",
            "correction_resistance_or_delay",
            "audit_attribution_difficulty",
            "adversarial_inducement_vulnerability",
            "long_horizon_task_instability",
            "misleading_context_vulnerability",
        ]:
            if candidate in instance_id:
                return candidate

        return ""

    def _extract_called_tools(
        self,
        trajectory: Optional[List[Dict[str, Any]]],
        runtime_state: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        if runtime_state and isinstance(runtime_state.get("called_tools"), list):
            return runtime_state["called_tools"]

        tools = []
        for item in trajectory or []:
            if not isinstance(item, dict):
                continue

            if "tool_name" in item:
                tools.append(item)
            elif isinstance(item.get("result"), dict) and "tool_name" in item["result"]:
                tools.append(item["result"])
            elif isinstance(item.get("observation"), dict) and "tool_name" in item["observation"]:
                tools.append(item["observation"])

        return tools
