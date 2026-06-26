from __future__ import annotations

from typing import Any, Dict, List, Optional

from scripts.expand.dimension_specs import autonomy_authority_failure
from scripts.expand.dimension_specs import goal_norm_misalignment
from scripts.expand.dimension_specs import interaction_understanding_failure


def build_output_shape(
    *,
    dimension: str,
    subtype: str,
    id_prefix: str,
    id_start_index: int,
) -> Optional[str]:
    if dimension == "autonomy_authority_failure":
        return autonomy_authority_failure.build_output_shape(
            subtype=subtype,
            id_prefix=id_prefix,
            id_start_index=id_start_index,
        )
    if dimension == "goal_norm_misalignment":
        return goal_norm_misalignment.build_output_shape(
            subtype=subtype,
            id_prefix=id_prefix,
            id_start_index=id_start_index,
        )
    if dimension in interaction_understanding_failure.INTERACTION_DIMENSIONS:
        return interaction_understanding_failure.build_output_shape(
            subtype=subtype,
            id_prefix=id_prefix,
            id_start_index=id_start_index,
        )
    return None


def sanitize_instance(
    instance: Dict[str, Any],
    *,
    dimension: str,
    subtype: str,
    sanitize_text,
    sanitize_payload,
) -> Dict[str, Any]:
    if dimension == "autonomy_authority_failure":
        return autonomy_authority_failure.sanitize_instance(
            instance,
            subtype=subtype,
            sanitize_text=sanitize_text,
            sanitize_payload=sanitize_payload,
        )
    return instance


def validate_instance(
    instance: Dict[str, Any],
    *,
    dimension: str,
    subtype: str,
) -> List[str]:
    if dimension == "autonomy_authority_failure":
        return autonomy_authority_failure.validate_instance(
            instance,
            subtype=subtype,
        )
    if dimension == "goal_norm_misalignment":
        return goal_norm_misalignment.validate_instance(
            instance,
            subtype=subtype,
        )
    if dimension in interaction_understanding_failure.INTERACTION_DIMENSIONS:
        return interaction_understanding_failure.validate_instance(
            instance,
            subtype=subtype,
        )
    return []


def validate_data(
    instances: List[Dict[str, Any]],
    *,
    dimension: str,
    subtype: str,
) -> List[str]:
    if dimension == "goal_norm_misalignment":
        return goal_norm_misalignment.validate_data(
            instances,
            subtype=subtype,
        )
    return []
