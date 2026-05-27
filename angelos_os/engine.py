from __future__ import annotations

import math
from typing import Dict, List, Optional

from .profiles import compile_profile, profile_summary
from .safety import SafetyGate
from .schemas import CandidateAction, CompiledProfile, DecisionOutput, FiveAnchorProfile, GateResult, Observation


class JudgmentCore:
    """
    Model-agnostic decision layer.
    Pipeline: simulate -> evaluate -> decide -> safety gate -> explain.
    """

    def __init__(self, safety_gate: SafetyGate | None = None):
        self.safety_gate = safety_gate or SafetyGate()

    def simulate(self, obs: Observation) -> List[CandidateAction]:
        scenario = str(obs.extra.get("scenario", ""))
        merge_mode = scenario == "merge_cutin"
        ped_mode = scenario == "ped_surprise"
        ped_ahead = float(obs.extra.get("ped_ahead", 0.0)) > 0.5

        keep_speed = CandidateAction(name="keep", steer=0.0, throttle=0.22, brake=0.0)
        slow = CandidateAction(name="slow_down", steer=0.0, throttle=0.05, brake=0.45)
        stop = CandidateAction(name="stop", steer=0.0, throttle=0.0, brake=0.9)

        if abs(obs.lane_offset) > 0.4:
            keep_speed = CandidateAction(name="lane_center", steer=-0.25 * obs.lane_offset, throttle=0.12, brake=0.2)
        if obs.red_light:
            keep_speed = CandidateAction(name="red_hold", steer=0.0, throttle=0.0, brake=0.85)
        if obs.ttc < 4.0 or obs.d_front < 12.0 or (ped_ahead and obs.d_ped < 8.0):
            slow = CandidateAction(name="risk_slow", steer=0.0, throttle=0.0, brake=0.6)
        if ped_mode:
            keep_speed = CandidateAction(name="ped_keep", steer=0.0, throttle=0.22, brake=max(keep_speed.brake, 0.0))
            slow = CandidateAction(name="ped_slow", steer=0.0, throttle=0.03, brake=max(slow.brake, 0.55))
            if ped_ahead:
                keep_speed = CandidateAction(name="ped_crawl", steer=0.0, throttle=0.14, brake=max(keep_speed.brake, 0.05))
                slow = CandidateAction(name="ped_yield", steer=0.0, throttle=0.02, brake=max(slow.brake, 0.68))
            if ped_ahead and obs.d_ped < 8.0:
                stop = CandidateAction(name="ped_stop", steer=0.0, throttle=0.0, brake=1.0)
        if merge_mode:
            keep_speed = CandidateAction(name="merge_keep", steer=0.0, throttle=0.14, brake=max(keep_speed.brake, 0.1))
            slow = CandidateAction(name="merge_yield", steer=0.0, throttle=0.0, brake=max(slow.brake, 0.7))
            if obs.ttc < 5.5 or obs.d_front < 18.0:
                stop = CandidateAction(name="merge_stop", steer=0.0, throttle=0.0, brake=1.0)
        return [keep_speed, slow, stop]

    def _drive_weights(self, obs: Observation, compiled_profile: Optional[CompiledProfile] = None) -> Dict[str, float]:
        scenario = str(obs.extra.get("scenario", ""))
        merge_mode = scenario == "merge_cutin"
        ped_mode = scenario == "ped_surprise"
        safety_ttc = 3.5 if not merge_mode else 5.0
        safety_front = 12.0 if not merge_mode else 18.0
        safety = self._clip01((safety_ttc - obs.ttc) / safety_ttc) + self._clip01((safety_front - obs.d_front) / safety_front)
        if ped_mode:
            ped_term = 0.0
            if float(obs.extra.get("ped_ahead", 0.0)) > 0.5:
                ped_term = min(1.0, self._clip01((18.0 - obs.d_ped) / 18.0) + 0.12)
            elif obs.d_ped < 8.0:
                ped_term = self._clip01((8.0 - obs.d_ped) / 8.0)
            safety += ped_term
        legality = 0.8 if obs.red_light else 0.2 + self._clip01(obs.overspeed / 20.0)
        comfort = 1.0 - self._clip01(abs(obs.lane_offset) / 1.5)
        efficiency = self._clip01((obs.visibility + 0.2)) * (1.0 - self._clip01(safety * 0.5))
        if merge_mode:
            efficiency *= 0.7
        if ped_mode:
            efficiency *= 0.75

        raw = {
            "safety": max(0.01, safety),
            "legality": max(0.01, legality),
            "comfort": max(0.01, comfort),
            "efficiency": max(0.01, efficiency),
        }
        base = self._normalize(raw)
        if compiled_profile is None:
            return base
        shifted = {
            key: base[key] + compiled_profile.drive_bias.get(key, 0.0)
            for key in ("safety", "legality", "comfort", "efficiency")
        }
        return self._normalize(shifted)

    def evaluate(
        self,
        obs: Observation,
        candidates: List[CandidateAction],
        compiled_profile: Optional[CompiledProfile] = None,
    ) -> tuple[Dict[str, float], Dict[str, float]]:
        drives = self._drive_weights(obs, compiled_profile=compiled_profile)
        scores: Dict[str, float] = {}
        for c in candidates:
            score = 0.0
            # Safety prefers lower throttle and higher brake when risk is high.
            score += drives["safety"] * (c.brake * 1.7 - c.throttle * 1.25)
            # Legality penalizes motion under red-light and overspeed.
            if obs.red_light:
                score += drives["legality"] * (c.brake * 1.25 - c.throttle * 1.1)
            else:
                score += drives["legality"] * (0.2 - 0.2 * c.brake)
            # Comfort prefers smooth actions.
            score += drives["comfort"] * (0.35 - 0.6 * abs(c.steer) - 0.45 * c.brake)
            # Efficiency prefers forward progress when safe.
            score += drives["efficiency"] * (c.throttle * 0.65 - c.brake * 0.85)
            if str(obs.extra.get("scenario", "")) == "merge_cutin":
                score += drives["safety"] * (0.15 if "yield" in c.name or "stop" in c.name else -0.1)
            if str(obs.extra.get("scenario", "")) == "ped_surprise":
                score += drives["safety"] * (0.10 if ("yield" in c.name or "stop" in c.name or "crawl" in c.name) else -0.06)
            scores[c.name] = score
        return scores, drives

    def decide(
        self,
        obs: Observation,
        profile: Optional[FiveAnchorProfile] = None,
        compiled_profile: Optional[CompiledProfile] = None,
        candidates: Optional[List[CandidateAction]] = None,
    ) -> DecisionOutput:
        compiled = self._resolve_profile(profile, compiled_profile)
        candidate_set = candidates if candidates is not None else self.simulate(obs)
        if not candidate_set:
            candidate_set = self.simulate(obs)
        scores, drives = self.evaluate(obs, candidate_set, compiled_profile=compiled)
        chosen = max(candidate_set, key=lambda c: scores[c.name])

        gate = self.safety_gate.evaluate(obs, compiled_profile=compiled)
        adjusted = self._apply_gate(chosen, gate)
        confidence = self._confidence(scores)

        why = [
            f"top_action={chosen.name} by drive-weighted score",
            f"gate_mode={gate.mode} ({gate.reason})",
            (
                "dominant_drive="
                + max(drives.items(), key=lambda item: item[1])[0]
                + f" ({max(drives.values()):.2f})"
            ),
        ]
        if compiled is not None:
            why.append(
                "profile_bias="
                + max(compiled.drive_bias.items(), key=lambda item: item[1])[0]
                + f" ({max(compiled.drive_bias.values()):.2f})"
            )
        counterfactual = self._counterfactual(obs, scores)
        highlights = []
        if compiled is not None:
            dominant_drive = max(drives.items(), key=lambda item: item[1])
            highlights = [
                f"profile={compiled.name or 'custom'}",
                f"scenario={str(obs.extra.get('scenario', 'custom_observation')) or 'custom_observation'}",
                f"selected={adjusted.name}",
                f"gate={gate.mode}",
                f"dominant_drive={dominant_drive[0]}({dominant_drive[1]:.2f})",
            ]

        return DecisionOutput(
            selected=adjusted,
            scores=scores,
            drives=drives,
            gate=gate,
            confidence=confidence,
            why=why,
            counterfactual=counterfactual,
            profile_summary=profile_summary(compiled) if compiled is not None else None,
            compiled_profile=compiled,
            decision_highlights=highlights,
        )

    @staticmethod
    def _resolve_profile(
        profile: Optional[FiveAnchorProfile],
        compiled_profile: Optional[CompiledProfile],
    ) -> Optional[CompiledProfile]:
        if compiled_profile is not None:
            return compiled_profile
        if profile is not None:
            return compile_profile(profile)
        return None

    @staticmethod
    def _apply_gate(action: CandidateAction, gate: GateResult) -> CandidateAction:
        throttle = action.throttle * gate.throttle_scale
        brake = max(action.brake, gate.force_brake_min)
        return CandidateAction(
            name=action.name if gate.mode == "allow" else f"{action.name}|{gate.mode}",
            steer=action.steer,
            throttle=max(0.0, min(1.0, throttle)),
            brake=max(0.0, min(1.0, brake)),
        )

    @staticmethod
    def _normalize(v: Dict[str, float]) -> Dict[str, float]:
        s = sum(v.values())
        if s <= 0:
            return {k: 1.0 / len(v) for k in v}
        return {k: val / s for k, val in v.items()}

    @staticmethod
    def _clip01(x: float) -> float:
        return max(0.0, min(1.0, x))

    @staticmethod
    def _confidence(scores: Dict[str, float]) -> float:
        vals = sorted(scores.values(), reverse=True)
        if len(vals) < 2:
            return 1.0
        gap = vals[0] - vals[1]
        return 1.0 / (1.0 + math.exp(-4.0 * gap))

    @staticmethod
    def _counterfactual(obs: Observation, scores: Dict[str, float]) -> str:
        if obs.ttc < 2.0:
            return "If TTC were higher, efficiency-driven actions would score better."
        if obs.red_light:
            return "If traffic light were green, throttle-heavy actions would be less penalized."
        return "If visibility were lower, safety weighting would further suppress throttle."


class SynOpticCore(JudgmentCore):
    """Public-facing name for the Angelos model-agnostic safety judgment core."""

    pass
