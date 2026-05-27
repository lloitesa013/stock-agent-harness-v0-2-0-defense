from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .schemas import CandidateAction, Observation


@dataclass
class ProviderCandidateBundle:
    provider_id: str
    display_name: str
    candidates: List[CandidateAction]
    provider_notes: List[str]


class ProviderAdapter:
    provider_id: str = "provider"
    display_name: str = "Provider"

    def propose(self, core, observation: Observation, scenario_id: str) -> ProviderCandidateBundle:
        raise NotImplementedError


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _transform_candidates(
    candidates: List[CandidateAction],
    *,
    throttle_scale: float,
    throttle_offset: float,
    brake_scale: float,
    brake_offset: float,
) -> List[CandidateAction]:
    transformed: List[CandidateAction] = []
    for candidate in candidates:
        transformed.append(
            CandidateAction(
                name=candidate.name,
                steer=candidate.steer,
                throttle=_clip01(candidate.throttle * throttle_scale + throttle_offset),
                brake=_clip01(candidate.brake * brake_scale + brake_offset),
            )
        )
    return transformed


class SionicLocalAdapter(ProviderAdapter):
    provider_id = "sionic_local"
    display_name = "Sionic Local Baseline"

    def propose(self, core, observation: Observation, scenario_id: str) -> ProviderCandidateBundle:
        candidates = core.simulate(observation)
        return ProviderCandidateBundle(
            provider_id=self.provider_id,
            display_name=self.display_name,
            candidates=candidates,
            provider_notes=["baseline local candidate generator"],
        )


class MockCautiousAdapter(ProviderAdapter):
    provider_id = "mock_cautious"
    display_name = "Mock Cautious Provider"

    def propose(self, core, observation: Observation, scenario_id: str) -> ProviderCandidateBundle:
        baseline = core.simulate(observation)
        return ProviderCandidateBundle(
            provider_id=self.provider_id,
            display_name=self.display_name,
            candidates=_transform_candidates(
                baseline,
                throttle_scale=0.55,
                throttle_offset=0.0,
                brake_scale=1.15,
                brake_offset=0.12,
            ),
            provider_notes=["deterministic cautious proposal bundle"],
        )


class MockFastAdapter(ProviderAdapter):
    provider_id = "mock_fast"
    display_name = "Mock Fast Provider"

    def propose(self, core, observation: Observation, scenario_id: str) -> ProviderCandidateBundle:
        baseline = core.simulate(observation)
        return ProviderCandidateBundle(
            provider_id=self.provider_id,
            display_name=self.display_name,
            candidates=_transform_candidates(
                baseline,
                throttle_scale=1.25,
                throttle_offset=0.08,
                brake_scale=0.65,
                brake_offset=-0.04,
            ),
            provider_notes=["deterministic progress-heavy proposal bundle"],
        )


_PROVIDERS: Dict[str, ProviderAdapter] = {
    adapter.provider_id: adapter
    for adapter in (SionicLocalAdapter(), MockCautiousAdapter(), MockFastAdapter())
}


def get_provider(provider_id: str) -> ProviderAdapter:
    if provider_id not in _PROVIDERS:
        raise ValueError(f"unknown provider_id: {provider_id}")
    return _PROVIDERS[provider_id]


def provider_catalog() -> List[Dict[str, str]]:
    return [
        {
            "id": adapter.provider_id,
            "display_name": adapter.display_name,
        }
        for adapter in _PROVIDERS.values()
    ]


def default_provider_ids() -> List[str]:
    return list(_PROVIDERS.keys())
