from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .engine import SynOpticCore
from .profiles import compile_profile, get_builtin_scenario
from .providers import default_provider_ids, get_provider, provider_catalog
from .schemas import CompiledProfile, FiveAnchorProfile

DEFAULT_VALIDATION_SCENARIO_IDS = [
    "chatbot_marketing_claim",
    "chatbot_sensitive_roster",
    "delivery_robot_human_crossing",
    "delivery_robot_tight_corridor",
]

INVARIANCE_TRANSFORMS = (
    "direct_compile",
    "profile_roundtrip",
    "compiled_roundtrip",
    "repeat_compile",
    "builtin_vs_inline",
)

REFERENCE_PROVIDER_ID = "sionic_local"


def _base_action_name(selected_name: str) -> str:
    return selected_name.split("|", 1)[0]


def _dominant_drive(decision: Any) -> Tuple[str, float]:
    return max(decision.drives.items(), key=lambda item: item[1])


def normalized_reason_tag(decision: Any, scenario_id: str) -> str:
    reason = str(decision.gate.reason).lower()
    selected = _base_action_name(decision.selected.name).lower()
    scenario = scenario_id.lower()
    if decision.gate.mode == "handoff" or "handoff" in reason:
        return "handoff"
    if "red light" in reason or "red_light" in scenario:
        return "red_light"
    if "collision" in reason or "imminent" in reason:
        return "collision"
    if "ped" in reason or "ped_" in selected or "ped" in scenario or "human_crossing" in scenario:
        return "pedestrian"
    if decision.gate.mode == "degrade" or "caution" in reason:
        return "caution"
    return "normal"


def decision_signature(decision: Any, scenario_id: str) -> Dict[str, Any]:
    dominant_drive, dominant_score = _dominant_drive(decision)
    reason_tag = normalized_reason_tag(decision, scenario_id)
    base_action = _base_action_name(decision.selected.name)
    return {
        "selected_action": decision.selected.name,
        "base_selected_action": base_action,
        "gate_mode": decision.gate.mode,
        "dominant_drive": dominant_drive,
        "dominant_drive_score": round(dominant_score, 4),
        "normalized_reason_tag": reason_tag,
        "comparison_key": f"{base_action}|{decision.gate.mode}|{dominant_drive}",
    }


def _candidate_summary(candidates: Iterable[Any]) -> List[Dict[str, Any]]:
    return [
        {
            "name": candidate.name,
            "throttle": round(candidate.throttle, 3),
            "brake": round(candidate.brake, 3),
            "steer": round(candidate.steer, 3),
        }
        for candidate in candidates
    ]


def _scenario_ids(input_ids: Optional[List[str]]) -> List[str]:
    scenario_ids = input_ids or list(DEFAULT_VALIDATION_SCENARIO_IDS)
    if not isinstance(scenario_ids, list) or not all(isinstance(item, str) for item in scenario_ids):
        raise ValueError("scenario_ids must be a list of strings")
    for scenario_id in scenario_ids:
        get_builtin_scenario(scenario_id)
    return scenario_ids


def _provider_ids(input_ids: Optional[List[str]]) -> List[str]:
    provider_ids = input_ids or default_provider_ids()
    if not isinstance(provider_ids, list) or not all(isinstance(item, str) for item in provider_ids):
        raise ValueError("provider_ids must be a list of strings")
    deduped: List[str] = []
    if REFERENCE_PROVIDER_ID not in provider_ids:
        provider_ids = [REFERENCE_PROVIDER_ID, *provider_ids]
    for provider_id in provider_ids:
        get_provider(provider_id)
        if provider_id not in deduped:
            deduped.append(provider_id)
    return deduped


def _metric_ratio(cases: List[Dict[str, Any]], key: str) -> float:
    applicable = [case for case in cases if case.get("applicable", True)]
    if not applicable:
        return 1.0
    hits = sum(1 for case in applicable if case[key])
    return round(hits / len(applicable), 4)


def _transform_summary(name: str, cases: List[Dict[str, Any]], applicable: bool) -> Dict[str, Any]:
    transform_cases = [case for case in cases if case["transform"] == name]
    return {
        "name": name,
        "applicable": applicable,
        "case_count": len(transform_cases),
        "metrics": {
            "schema_round_trip_fidelity": _metric_ratio(transform_cases, "schema_match"),
            "policy_preservation_rate": _metric_ratio(transform_cases, "policy_match"),
            "veto_consistency": _metric_ratio(transform_cases, "veto_match"),
            "trace_alignment": _metric_ratio(transform_cases, "trace_match"),
        },
    }


def _make_invariance_case(
    transform: str,
    scenario_id: str,
    reference_decision: Any,
    candidate_decision: Any,
    reference_profile: FiveAnchorProfile,
    candidate_profile: FiveAnchorProfile,
    reference_compiled: CompiledProfile,
    candidate_compiled: CompiledProfile,
) -> Dict[str, Any]:
    reference_signature = decision_signature(reference_decision, scenario_id)
    candidate_signature = decision_signature(candidate_decision, scenario_id)
    return {
        "transform": transform,
        "scenario_id": scenario_id,
        "applicable": True,
        "schema_match": (
            reference_profile.profile_fingerprint == candidate_profile.profile_fingerprint
            and reference_compiled.profile_fingerprint == candidate_compiled.profile_fingerprint
            and reference_profile.schema_version == candidate_profile.schema_version
            and reference_compiled.schema_version == candidate_compiled.schema_version
            and reference_compiled.compiler_version == candidate_compiled.compiler_version
        ),
        "policy_match": reference_signature["comparison_key"] == candidate_signature["comparison_key"],
        "veto_match": reference_signature["gate_mode"] == candidate_signature["gate_mode"],
        "trace_match": (
            reference_signature["dominant_drive"] == candidate_signature["dominant_drive"]
            and reference_signature["normalized_reason_tag"] == candidate_signature["normalized_reason_tag"]
        ),
        "reference": reference_signature,
        "candidate": candidate_signature,
    }


def _invariance_report_markdown(
    profile: FiveAnchorProfile,
    scenario_ids: List[str],
    metrics: Dict[str, float],
    transforms: List[Dict[str, Any]],
) -> str:
    lines = [
        f"- validation: CCP invariance",
        f"- profile: {profile.name or 'custom'}",
        f"- schema_version: {profile.schema_version}",
        f"- scenarios: {', '.join(scenario_ids)}",
        f"- schema_round_trip_fidelity: {metrics['schema_round_trip_fidelity']:.2f}",
        f"- policy_preservation_rate: {metrics['policy_preservation_rate']:.2f}",
        f"- veto_consistency: {metrics['veto_consistency']:.2f}",
        f"- trace_alignment: {metrics['trace_alignment']:.2f}",
    ]
    for transform in transforms:
        if transform["applicable"]:
            lines.append(
                f"- {transform['name']}: policy={transform['metrics']['policy_preservation_rate']:.2f}, "
                f"veto={transform['metrics']['veto_consistency']:.2f}"
            )
    return "\n".join(lines)


def validate_invariance(
    profile: FiveAnchorProfile,
    compiled_profile: Optional[CompiledProfile] = None,
    *,
    source_profile_id: Optional[str] = None,
    scenario_ids: Optional[List[str]] = None,
    core: Optional[SynOpticCore] = None,
) -> Dict[str, Any]:
    validation_core = core or SynOpticCore()
    resolved_compiled = compiled_profile or compile_profile(profile)
    scenarios = _scenario_ids(scenario_ids)

    reference_decisions = {
        scenario_id: validation_core.decide(get_builtin_scenario(scenario_id), compiled_profile=resolved_compiled)
        for scenario_id in scenarios
    }

    transforms_meta: List[Dict[str, Any]] = []
    cases: List[Dict[str, Any]] = []

    for transform in INVARIANCE_TRANSFORMS:
        applicable = transform != "builtin_vs_inline" or source_profile_id is not None
        transforms_meta.append({"name": transform, "applicable": applicable})
        if not applicable:
            continue

        transformed_profile = profile
        transformed_compiled = resolved_compiled
        if transform == "direct_compile":
            transformed_profile = FiveAnchorProfile.from_dict(profile.to_dict())
            transformed_compiled = compile_profile(transformed_profile)
        elif transform == "profile_roundtrip":
            transformed_profile = FiveAnchorProfile.from_dict(profile.to_dict())
            transformed_compiled = compile_profile(transformed_profile)
        elif transform == "compiled_roundtrip":
            transformed_profile = FiveAnchorProfile.from_dict(profile.to_dict())
            transformed_compiled = CompiledProfile.from_dict(resolved_compiled.to_dict())
        elif transform == "repeat_compile":
            transformed_profile = FiveAnchorProfile.from_dict(profile.to_dict())
            transformed_compiled = compile_profile(transformed_profile)
        elif transform == "builtin_vs_inline":
            transformed_profile = FiveAnchorProfile.from_dict(profile.to_dict())
            transformed_compiled = compile_profile(transformed_profile)

        for scenario_id in scenarios:
            obs = get_builtin_scenario(scenario_id)
            candidate_decision = validation_core.decide(obs, compiled_profile=transformed_compiled)
            cases.append(
                _make_invariance_case(
                    transform,
                    scenario_id,
                    reference_decisions[scenario_id],
                    candidate_decision,
                    profile,
                    transformed_profile,
                    resolved_compiled,
                    transformed_compiled,
                )
            )

    transform_summaries = [
        _transform_summary(meta["name"], cases, meta["applicable"])
        for meta in transforms_meta
    ]
    metrics = {
        "schema_round_trip_fidelity": _metric_ratio(cases, "schema_match"),
        "policy_preservation_rate": _metric_ratio(cases, "policy_match"),
        "veto_consistency": _metric_ratio(cases, "veto_match"),
        "trace_alignment": _metric_ratio(cases, "trace_match"),
    }
    return {
        "profile": profile.to_dict(),
        "compiled_profile": resolved_compiled.to_dict(),
        "scenario_ids": scenarios,
        "transforms": transform_summaries,
        "metrics": metrics,
        "cases": cases,
        "report_markdown": _invariance_report_markdown(profile, scenarios, metrics, transform_summaries),
    }


def _provider_report_markdown(
    profile: FiveAnchorProfile,
    scenario_ids: List[str],
    metrics: Dict[str, Any],
) -> str:
    lines = [
        f"- validation: cross-provider portability",
        f"- profile: {profile.name or 'custom'}",
        f"- reference_provider: {REFERENCE_PROVIDER_ID}",
        f"- scenarios: {', '.join(scenario_ids)}",
        f"- overall_policy_preservation_rate: {metrics['overall']['policy_preservation_rate']:.2f}",
        f"- overall_veto_consistency: {metrics['overall']['veto_consistency']:.2f}",
        f"- overall_trace_alignment: {metrics['overall']['trace_alignment']:.2f}",
    ]
    for provider_id, provider_metrics in metrics["by_provider"].items():
        lines.append(
            f"- {provider_id}: policy={provider_metrics['policy_preservation_rate']:.2f}, "
            f"veto={provider_metrics['veto_consistency']:.2f}, drift={provider_metrics['provider_drift_score']:.2f}"
        )
    return "\n".join(lines)


def validate_provider_portability(
    profile: FiveAnchorProfile,
    compiled_profile: Optional[CompiledProfile] = None,
    *,
    scenario_ids: Optional[List[str]] = None,
    provider_ids: Optional[List[str]] = None,
    core: Optional[SynOpticCore] = None,
) -> Dict[str, Any]:
    validation_core = core or SynOpticCore()
    resolved_compiled = compiled_profile or compile_profile(profile)
    scenarios = _scenario_ids(scenario_ids)
    providers = _provider_ids(provider_ids)

    reference_adapter = get_provider(REFERENCE_PROVIDER_ID)
    cases: List[Dict[str, Any]] = []

    for scenario_id in scenarios:
        obs = get_builtin_scenario(scenario_id)
        reference_bundle = reference_adapter.propose(validation_core, obs, scenario_id)
        reference_decision = validation_core.decide(
            obs,
            compiled_profile=resolved_compiled,
            candidates=reference_bundle.candidates,
        )
        reference_signature = decision_signature(reference_decision, scenario_id)
        for provider_id in providers:
            if provider_id == REFERENCE_PROVIDER_ID:
                continue
            adapter = get_provider(provider_id)
            bundle = adapter.propose(validation_core, obs, scenario_id)
            decision = validation_core.decide(
                obs,
                compiled_profile=resolved_compiled,
                candidates=bundle.candidates,
            )
            signature = decision_signature(decision, scenario_id)
            cases.append(
                {
                    "scenario_id": scenario_id,
                    "provider_id": provider_id,
                    "provider_display_name": adapter.display_name,
                    "policy_match": reference_signature["comparison_key"] == signature["comparison_key"],
                    "veto_match": reference_signature["gate_mode"] == signature["gate_mode"],
                    "trace_match": (
                        reference_signature["dominant_drive"] == signature["dominant_drive"]
                        and reference_signature["normalized_reason_tag"] == signature["normalized_reason_tag"]
                    ),
                    "reference": reference_signature,
                    "candidate": signature,
                    "provider_notes": bundle.provider_notes,
                    "candidate_bundle": _candidate_summary(bundle.candidates),
                }
            )

    by_provider_cases: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for case in cases:
        by_provider_cases[case["provider_id"]].append(case)

    by_provider_metrics = {}
    for provider_id, provider_cases in by_provider_cases.items():
        policy_rate = _metric_ratio(provider_cases, "policy_match")
        by_provider_metrics[provider_id] = {
            "policy_preservation_rate": policy_rate,
            "veto_consistency": _metric_ratio(provider_cases, "veto_match"),
            "trace_alignment": _metric_ratio(provider_cases, "trace_match"),
            "provider_drift_score": round(1.0 - policy_rate, 4),
        }

    overall_policy = _metric_ratio(cases, "policy_match")
    metrics = {
        "overall": {
            "policy_preservation_rate": overall_policy,
            "veto_consistency": _metric_ratio(cases, "veto_match"),
            "trace_alignment": _metric_ratio(cases, "trace_match"),
            "provider_drift_score": round(1.0 - overall_policy, 4),
        },
        "by_provider": by_provider_metrics,
    }

    return {
        "reference_provider": REFERENCE_PROVIDER_ID,
        "providers": provider_catalog(),
        "scenario_ids": scenarios,
        "metrics": metrics,
        "cases": cases,
        "report_markdown": _provider_report_markdown(profile, scenarios, metrics),
    }
