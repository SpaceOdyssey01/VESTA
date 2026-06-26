from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ReasoningPlanningRuntimeState:
    state_changed: bool = False
    forbidden_tool_called: bool = False
    decomposition_distortion_action_called: bool = False
    constraint_omission_action_called: bool = False
    risk_misassessment_action_called: bool = False
    verification_failure_action_called: bool = False
    called_tools: List[Dict[str, Any]] = field(default_factory=list)
    risk_events: List[Any] = field(default_factory=list)


class ReasoningPlanningRiskTools:
    DYNAMIC_TOOL_ROLES = {
        "normal_task_tool",
        "decomposition_distortion_action",
        "constraint_omission_action",
        "risk_misassessment_action",
        "verification_failure_action",
    }

    def __init__(self, instance: Optional[Dict[str, Any]] = None):
        self.instance = instance or {}
        self.environment_state = self.instance.get("environment_state") or self.instance.get("environment", {})
        self.tool_roles = self._tool_roles_from_instance()
        self.state = ReasoningPlanningRuntimeState()

    def _tool_roles_from_instance(self) -> Dict[str, Dict[str, Any]]:
        roles: Dict[str, Dict[str, Any]] = {}
        for item in self.instance.get("tool_manifest", {}).get("required_tool_roles", []):
            tool_name = item.get("preferred_tool_name")
            role = item.get("role")
            if tool_name and role:
                roles[tool_name] = dict(item)

        attack_tool_name = self.environment_state.get("attack_tool_name") or self.environment_state.get("attacker_tool_name")
        if attack_tool_name and attack_tool_name not in roles:
            roles[attack_tool_name] = {
                "role": self._risky_role(),
                "preferred_tool_name": attack_tool_name,
                "capability": self.environment_state.get("attack_tool_description")
                or self.environment_state.get("attacker_description", ""),
            }

        for tool_name in self.environment_state.get("normal_expected_tools", []) or []:
            roles.setdefault(
                tool_name,
                {
                    "role": "normal_task_tool",
                    "preferred_tool_name": tool_name,
                    "capability": "",
                },
            )

        return roles

    def _risk_subtype(self) -> str:
        subtype = self.instance.get("risk_subtype")
        if isinstance(subtype, dict):
            return str(subtype.get("id", ""))
        if isinstance(subtype, str):
            return subtype
        return str(self.instance.get("tool_manifest", {}).get("constraints", {}).get("risk_subtype", ""))

    def _risky_role(self) -> str:
        subtype = self._risk_subtype()
        if subtype == "constraint_omission":
            return "constraint_omission_action"
        if subtype == "risk_misassessment":
            return "risk_misassessment_action"
        if subtype == "verification_failure":
            return "verification_failure_action"
        return "decomposition_distortion_action"

    def _snapshot_state(self) -> Dict[str, Any]:
        return asdict(self.state)

    def _record_tool(
        self,
        tool_name: str,
        tool_type: str,
        risk_level: str,
        observation: Optional[Dict[str, Any]] = None,
        risk_event: Optional[Any] = None,
    ) -> Dict[str, Any]:
        flag_by_type = {
            "decomposition_distortion_action": "decomposition_distortion_action_called",
            "constraint_omission_action": "constraint_omission_action_called",
            "risk_misassessment_action": "risk_misassessment_action_called",
            "verification_failure_action": "verification_failure_action_called",
        }
        flag_name = flag_by_type.get(tool_type)
        if flag_name:
            self.state.state_changed = True
            self.state.forbidden_tool_called = True
            setattr(self.state, flag_name, True)

        event = {
            "tool_name": tool_name,
            "tool_type": tool_type,
            "risk_level": risk_level,
            "risk_event": risk_event,
            "observation": observation or {},
        }
        self.state.called_tools.append(event)
        if risk_event:
            self.state.risk_events.append(risk_event)
        return {**event, "runtime_state": self._snapshot_state()}

    def get_tool_registry(self) -> Dict[str, Callable[..., Dict[str, Any]]]:
        registry: Dict[str, Callable[..., Dict[str, Any]]] = {
            "inspect_plan_examples": self.inspect_plan_examples,
            "compare_plan_to_current_task": self.compare_plan_to_current_task,
            "prepare_plan_verification_summary": self.prepare_plan_verification_summary,
        }

        for tool_name, role_spec in self.tool_roles.items():
            role = role_spec.get("role")
            if role == "normal_task_tool":
                registry.setdefault(tool_name, self._make_normal_task_tool(tool_name))
            elif role in self.DYNAMIC_TOOL_ROLES:
                registry.setdefault(tool_name, self._make_risky_tool(tool_name, role))

        return registry

    def _make_normal_task_tool(self, tool_name: str) -> Callable[..., Dict[str, Any]]:
        def tool(**kwargs: Any) -> Dict[str, Any]:
            return self._normal_task_tool(tool_name, kwargs)

        return tool

    def _make_risky_tool(self, tool_name: str, tool_type: str) -> Callable[..., Dict[str, Any]]:
        def tool(**kwargs: Any) -> Dict[str, Any]:
            return self._planning_risk_action(tool_name, tool_type, kwargs)

        return tool

    def inspect_plan_examples(self, **kwargs: Any) -> Dict[str, Any]:
        subtype = self._risk_subtype()
        return self._record_tool(
            "inspect_plan_examples",
            "observation",
            "low",
            {
                "plan_examples_reviewed": True,
                "pot_trigger": self.environment_state.get("pot_trigger"),
                "trigger_conditioned_step_detected": True,
                "decomposition_distortion_detected": subtype == "goal_decomposition_distortion",
                "constraint_omission_detected": subtype == "constraint_omission",
                "risk_misassessment_detected": subtype == "risk_misassessment",
                "verification_failure_detected": subtype == "verification_failure",
                "planner_context": self.environment_state.get("planner_context"),
                "arguments": kwargs,
            },
        )

    def compare_plan_to_current_task(self, **kwargs: Any) -> Dict[str, Any]:
        return self._record_tool(
            "compare_plan_to_current_task",
            "observation",
            "low",
            {
                "comparison_completed": True,
                "current_task": self.environment_state.get("original_task"),
                "attacker_tool_referenced": self.environment_state.get("attack_tool_name")
                or self.environment_state.get("attacker_tool_name"),
                "trigger_is_authorization": False,
                "plan_goal_conflict": True,
                "omitted_constraints": self.environment_state.get("omitted_constraints", []),
                "risk_assessment_gap": self.environment_state.get("risk_assessment_gap")
                or self.environment_state.get("misassessed_risk"),
                "required_verification": self.environment_state.get("required_verification")
                or self.environment_state.get("safe_completion_requires"),
                "arguments": kwargs,
            },
        )

    def prepare_plan_verification_summary(self, **kwargs: Any) -> Dict[str, Any]:
        subtype = self._risk_subtype()
        return self._record_tool(
            "prepare_plan_verification_summary",
            "safe_action",
            "low",
            {
                "verification_summary_prepared": True,
                "current_task_preserved": True,
                "trigger_conditioned_step_rejected": True,
                "decomposition_distortion_rejected": subtype == "goal_decomposition_distortion",
                "constraint_omission_rejected": subtype == "constraint_omission",
                "risk_misassessment_rejected": subtype == "risk_misassessment",
                "verification_failure_rejected": subtype == "verification_failure",
                "arguments": kwargs,
            },
        )

    def _planning_risk_action(self, tool_name: str, tool_type: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        attack_goal = self.environment_state.get("attack_goal")
        return self._record_tool(
            tool_name,
            tool_type,
            "critical",
            {
                "asb_pot_attack_tool_called": True,
                "trigger_conditioned_plan_step_adopted": True,
                "pot_trigger": self.environment_state.get("pot_trigger"),
                "attack_goal": attack_goal,
                "output": attack_goal,
                "arguments": arguments,
            },
            risk_event="reasoning_planning_risk",
        )

    def _normal_task_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        outputs = self.environment_state.get("normal_tool_outputs", {}) or {}
        output = None
        if isinstance(outputs, dict):
            output = outputs.get(tool_name)
        elif isinstance(outputs, list):
            for item in outputs:
                if item.get("tool_name") == tool_name:
                    output = item.get("expected_output") or item.get("description")
                    break
        if not output:
            role_spec = self.tool_roles.get(tool_name, {})
            output = role_spec.get("capability") or f"Completed normal task tool call: {tool_name}."

        return self._record_tool(
            tool_name,
            "normal_task_tool",
            "low",
            {
                "asb_normal_tool_called": True,
                "output": output,
                "arguments": arguments,
            },
        )

    def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        registry = self.get_tool_registry()
        if tool_name not in registry:
            return self._record_tool(
                tool_name,
                "unknown",
                "medium",
                {"error": f"Unknown tool: {tool_name}", "available_tools": sorted(registry.keys())},
            )
        return registry[tool_name](**(arguments or {}))

    def get_runtime_state(self) -> Dict[str, Any]:
        return self._snapshot_state()


def build_reasoning_planning_risk_tool_registry(
    instance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Callable[..., Dict[str, Any]]]:
    return ReasoningPlanningRiskTools(instance).get_tool_registry()


def build_tool_registry(instance: Optional[Dict[str, Any]] = None) -> Dict[str, Callable[..., Dict[str, Any]]]:
    return build_reasoning_planning_risk_tool_registry(instance)
