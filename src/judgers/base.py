from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


VALID_LABELS = {"safe", "unsafe", "uncertain"}


@dataclass
class BaseJudgerResult:
    label: str
    risk_subtype: str = ""
    risk_points: List[str] = field(default_factory=list)
    safe_points: List[str] = field(default_factory=list)
    reason: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    confidence: Optional[float] = None
    judge_type: str = "rule"

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)

        if data["label"] not in VALID_LABELS:
            data["label"] = "uncertain"

        if data["confidence"] is not None:
            data["confidence"] = max(0.0, min(1.0, float(data["confidence"])))

        return data


class BaseJudger(ABC):
    judger_name: str = "base_judger"

    @abstractmethod
    def judge(
        self,
        instance: Dict[str, Any],
        trajectory: Optional[List[Dict[str, Any]]] = None,
        runtime_state: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        raise NotImplementedError

    def normalize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        label = result.get("label", "uncertain")
        if label not in VALID_LABELS:
            label = "uncertain"

        risk_points = result.get("risk_points", [])
        if not isinstance(risk_points, list):
            risk_points = [str(risk_points)]

        safe_points = result.get("safe_points", [])
        if not isinstance(safe_points, list):
            safe_points = [str(safe_points)]

        evidence = result.get("evidence", {})
        if evidence is None:
            evidence = {}

        normalized = {
            **result,
            "label": label,
            "risk_points": risk_points,
            "safe_points": safe_points,
            "evidence": evidence
        }

        if "judge_type" not in normalized:
            normalized["judge_type"] = "rule"

        return normalized