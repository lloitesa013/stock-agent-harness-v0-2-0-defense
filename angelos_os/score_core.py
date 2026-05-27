from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .engine import JudgmentCore
from .schemas import CandidateAction, CompiledProfile, GateResult, Observation


@dataclass
class ScoreSafetyConfig:
    hard_ttc: float = 0.65
    caution_ttc: float = 2.6
    handoff_ttc: float = 0.45
    front_stop_distance: float = 4.2
    front_caution_distance: float = 9.0
    ped_stop_distance: float = 4.0
    ped_caution_distance: float = 11.0
    red_light_speed_limit: float = 0.5
    low_visibility_threshold: float = 0.12
    overspeed_caution: float = 15.0


class ScoreSafetyGate:
    def __init__(self, config: Optional[ScoreSafetyConfig] = None):
        self.config = config or ScoreSafetyConfig()

    def evaluate(self, obs: Observation, compiled_profile: Optional[CompiledProfile] = None) -> GateResult:
        c = self.config
        scenario = str(obs.extra.get("scenario", ""))
        merge_mode = scenario == "merge_cutin"
        ped_mode = scenario == "ped_surprise"
        ped_ahead = float(obs.extra.get("ped_ahead", 0.0)) > 0.5
        gate_bias = compiled_profile.gate_bias if compiled_profile is not None else None
        profile_reason_suffix = ""
        if gate_bias is not None:
            has_guard_shift = any(
                (
                    gate_bias.caution_ttc_delta > 0.0,
                    gate_bias.hard_ttc_delta > 0.0,
                    gate_bias.front_caution_distance_delta > 0.0,
                    gate_bias.ped_caution_distance_delta > 0.0,
                    gate_bias.overspeed_caution_delta < 0.0,
                )
            )
            if has_guard_shift:
                profile_reason_suffix = " with profile guard bias"

        caution_ttc = c.caution_ttc + (0.2 if merge_mode else 0.0)
        hard_ttc = c.hard_ttc
        front_stop_distance = c.front_stop_distance + (0.4 if merge_mode else 0.0)
        front_caution_distance = c.front_caution_distance + (1.5 if merge_mode else 0.0)
        ped_stop_distance = c.ped_stop_distance + (0.4 if ped_mode else 0.0)
        ped_caution_distance = c.ped_caution_distance + (1.0 if ped_mode else 0.0)
        overspeed_caution = c.overspeed_caution

        if gate_bias is not None:
            caution_ttc += max(0.0, gate_bias.caution_ttc_delta)
            hard_ttc += max(0.0, gate_bias.hard_ttc_delta)
            front_caution_distance += max(0.0, gate_bias.front_caution_distance_delta)
            ped_caution_distance += max(0.0, gate_bias.ped_caution_distance_delta)
            overspeed_caution = max(0.5, overspeed_caution + min(0.0, gate_bias.overspeed_caution_delta))

        if obs.ttc <= c.handoff_ttc:
            return GateResult(
                mode="handoff",
                reason=f"ttc={obs.ttc:.2f} below handoff threshold",
                throttle_scale=0.0,
                force_brake_min=1.0,
                require_human_handoff=True,
            )

        if obs.ttc <= hard_ttc or obs.d_front <= front_stop_distance:
            return GateResult(
                mode="deny",
                reason=f"imminent collision risk{profile_reason_suffix}",
                throttle_scale=0.0,
                force_brake_min=0.9,
                require_human_handoff=False,
            )

        if obs.d_ped <= ped_stop_distance:
            return GateResult(
                mode="deny",
                reason=f"pedestrian proximity hard stop{profile_reason_suffix}",
                throttle_scale=0.0,
                force_brake_min=1.0,
                require_human_handoff=False,
            )

        if obs.red_light and obs.speed_kmh > c.red_light_speed_limit:
            return GateResult(
                mode="deny",
                reason=f"red light violation risk{profile_reason_suffix}",
                throttle_scale=0.0,
                force_brake_min=0.95,
                require_human_handoff=False,
            )

        if obs.red_light:
            return GateResult(
                mode="degrade",
                reason=f"red light hold mode{profile_reason_suffix}",
                throttle_scale=0.0,
                force_brake_min=0.8,
                require_human_handoff=False,
            )

        if (
            obs.ttc <= caution_ttc
            or obs.d_front <= front_caution_distance
            or (ped_ahead and obs.d_ped <= ped_caution_distance)
            or (ped_ahead and obs.d_ped <= 8.0)
            or obs.visibility <= c.low_visibility_threshold
            or (obs.overspeed >= overspeed_caution and obs.visibility <= 0.4)
        ):
            throttle_scale = 0.34 if merge_mode else (0.30 if ped_mode else 0.42)
            force_brake_min = 0.16 if merge_mode else (0.18 if ped_mode else 0.12)
            if gate_bias is not None:
                throttle_scale = min(0.75, throttle_scale + max(0.0, gate_bias.degrade_throttle_bonus))
                force_brake_min = max(0.05, force_brake_min - max(0.0, gate_bias.degrade_brake_relief))
            return GateResult(
                mode="degrade",
                reason=(
                    f"merge caution mode{profile_reason_suffix}"
                    if merge_mode
                    else (
                        f"ped caution mode{profile_reason_suffix}"
                        if ped_mode
                        else f"score caution mode{profile_reason_suffix}"
                    )
                ),
                throttle_scale=throttle_scale,
                force_brake_min=force_brake_min,
                require_human_handoff=False,
            )

        return GateResult(mode="allow", reason="normal operation")


class ScoreJudgmentCore(JudgmentCore):
    def __init__(self, safety_gate: ScoreSafetyGate | None = None):
        super().__init__(safety_gate=safety_gate or ScoreSafetyGate())

    @staticmethod
    def _clamp(value: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, value))

    def simulate(self, obs: Observation) -> List[CandidateAction]:
        scenario = str(obs.extra.get("scenario", ""))
        merge_mode = scenario == "merge_cutin"
        ped_mode = scenario == "ped_surprise"
        ped_ahead = float(obs.extra.get("ped_ahead", 0.0)) > 0.5
        steer_bias = self._clamp(-0.24 * obs.lane_offset, -0.35, 0.35)

        keep = CandidateAction(name="keep", steer=steer_bias, throttle=0.38, brake=0.0)
        commit = CandidateAction(name="commit", steer=steer_bias, throttle=0.58, brake=0.0)
        aligned_cruise = CandidateAction(name="aligned_cruise", steer=steer_bias * 0.82, throttle=0.78, brake=0.0)
        sprint_commit = CandidateAction(name="sprint_commit", steer=steer_bias, throttle=0.72, brake=0.0)
        late_brake_keep = CandidateAction(name="late_brake_keep", steer=steer_bias, throttle=0.34, brake=0.06)
        assertive_follow = CandidateAction(name="assertive_follow", steer=steer_bias, throttle=0.50, brake=0.02)
        crawl_commit = CandidateAction(name="crawl_commit", steer=steer_bias, throttle=0.26, brake=0.0)
        yield_soft = CandidateAction(name="yield_soft", steer=steer_bias, throttle=0.06, brake=0.28)
        stop_hard = CandidateAction(name="stop_hard", steer=0.0, throttle=0.0, brake=0.95)

        if abs(obs.lane_offset) > 0.4:
            center_steer = self._clamp(-0.35 * obs.lane_offset, -0.45, 0.45)
            keep = CandidateAction(name="keep", steer=center_steer, throttle=0.30, brake=0.0)
            commit = CandidateAction(name="commit", steer=center_steer, throttle=0.45, brake=0.0)
            aligned_cruise = CandidateAction(name="aligned_cruise", steer=center_steer, throttle=0.50, brake=0.0)
            sprint_commit = CandidateAction(name="sprint_commit", steer=center_steer, throttle=0.52, brake=0.0)
            late_brake_keep = CandidateAction(name="late_brake_keep", steer=center_steer, throttle=0.26, brake=0.06)
            assertive_follow = CandidateAction(name="assertive_follow", steer=center_steer, throttle=0.40, brake=0.02)
            crawl_commit = CandidateAction(name="crawl_commit", steer=center_steer, throttle=0.22, brake=0.0)
            yield_soft = CandidateAction(name="yield_soft", steer=center_steer, throttle=0.04, brake=0.26)

        if merge_mode:
            aligned_cruise = CandidateAction(name="aligned_cruise", steer=aligned_cruise.steer, throttle=0.68, brake=0.0)
            sprint_commit = CandidateAction(name="sprint_commit", steer=sprint_commit.steer, throttle=0.64, brake=0.0)
            assertive_follow = CandidateAction(name="assertive_follow", steer=assertive_follow.steer, throttle=0.56, brake=0.01)
            crawl_commit = CandidateAction(name="crawl_commit", steer=crawl_commit.steer, throttle=0.30, brake=0.0)
            yield_soft = CandidateAction(name="yield_soft", steer=yield_soft.steer, throttle=0.08, brake=0.22)

        if ped_mode:
            crawl_commit = CandidateAction(name="crawl_commit", steer=crawl_commit.steer, throttle=0.16, brake=0.02)
            yield_soft = CandidateAction(name="yield_soft", steer=yield_soft.steer, throttle=0.0, brake=0.45)

        if ped_ahead:
            commit = CandidateAction(name="commit", steer=commit.steer, throttle=0.16, brake=0.10)
            aligned_cruise = CandidateAction(name="aligned_cruise", steer=aligned_cruise.steer, throttle=0.14, brake=0.14)
            sprint_commit = CandidateAction(name="sprint_commit", steer=sprint_commit.steer, throttle=0.12, brake=0.16)
            assertive_follow = CandidateAction(name="assertive_follow", steer=assertive_follow.steer, throttle=0.18, brake=0.12)
            crawl_commit = CandidateAction(name="crawl_commit", steer=crawl_commit.steer, throttle=0.12, brake=max(crawl_commit.brake, 0.05))

        if obs.red_light:
            commit = CandidateAction(name="commit", steer=commit.steer, throttle=0.12, brake=0.20)
            aligned_cruise = CandidateAction(name="aligned_cruise", steer=aligned_cruise.steer, throttle=0.08, brake=0.28)
            sprint_commit = CandidateAction(name="sprint_commit", steer=sprint_commit.steer, throttle=0.08, brake=0.28)
            assertive_follow = CandidateAction(name="assertive_follow", steer=assertive_follow.steer, throttle=0.10, brake=0.25)

        if obs.ttc < 2.5 or obs.d_front < 8.0:
            commit = CandidateAction(name="commit", steer=commit.steer, throttle=0.18, brake=0.14)
            aligned_cruise = CandidateAction(name="aligned_cruise", steer=aligned_cruise.steer, throttle=0.16, brake=0.16)
            sprint_commit = CandidateAction(name="sprint_commit", steer=sprint_commit.steer, throttle=0.14, brake=0.18)
            assertive_follow = CandidateAction(name="assertive_follow", steer=assertive_follow.steer, throttle=0.22, brake=0.12)
            late_brake_keep = CandidateAction(name="late_brake_keep", steer=late_brake_keep.steer, throttle=0.16, brake=0.18)
            yield_soft = CandidateAction(name="yield_soft", steer=yield_soft.steer, throttle=0.03, brake=0.42)

        return [keep, commit, aligned_cruise, sprint_commit, late_brake_keep, assertive_follow, crawl_commit, yield_soft, stop_hard]

    def _drive_weights(self, obs: Observation, compiled_profile: Optional[CompiledProfile] = None) -> Dict[str, float]:
        base = super()._drive_weights(obs, compiled_profile=compiled_profile)
        ped_close = float(obs.extra.get("ped_ahead", 0.0)) > 0.5 and obs.d_ped < 10.0
        shifted = {
            "safety": base["safety"] * 0.72,
            "legality": base["legality"] * 0.92,
            "comfort": base["comfort"] * 0.38,
            "efficiency": base["efficiency"] * 2.75,
        }
        if obs.red_light:
            shifted["legality"] *= 1.45
            shifted["efficiency"] *= 0.20
        if obs.ttc < 3.5 or obs.d_front < 12.0 or ped_close:
            shifted["safety"] *= 1.18
            shifted["efficiency"] *= 0.82
            shifted["comfort"] *= 0.90
        return self._normalize(shifted)

    def evaluate(
        self,
        obs: Observation,
        candidates: List[CandidateAction],
        compiled_profile: Optional[CompiledProfile] = None,
    ) -> tuple[Dict[str, float], Dict[str, float]]:
        drives = self._drive_weights(obs, compiled_profile=compiled_profile)
        scores: Dict[str, float] = {}
        ped_close = float(obs.extra.get("ped_ahead", 0.0)) > 0.5 and obs.d_ped < 10.0
        safe_commit_window = not obs.red_light and not ped_close and obs.ttc >= 3.2 and obs.d_front >= 12.0
        moderate_risk = obs.ttc < 2.8 or obs.d_front < 9.0 or ped_close
        merge_mode = str(obs.extra.get("scenario", "")) == "merge_cutin"

        for c in candidates:
            score = 0.0
            score += drives["safety"] * (c.brake * 1.05 - c.throttle * 0.45)
            if obs.red_light:
                score += drives["legality"] * (c.brake * 1.6 - c.throttle * 1.4)
            else:
                score += drives["legality"] * (0.12 - 0.08 * c.brake - 0.05 * c.throttle * self._clip01(obs.overspeed))
            score += drives["comfort"] * (0.10 - 0.18 * abs(c.steer) - 0.12 * c.brake)
            score += drives["efficiency"] * (c.throttle * 1.85 - c.brake * 0.25)

            if safe_commit_window and c.name in {"commit", "aligned_cruise", "assertive_follow", "sprint_commit"}:
                score += 0.50 if c.name == "aligned_cruise" else (0.44 if c.name == "sprint_commit" else (0.35 if c.name == "commit" else 0.28))
            if safe_commit_window and merge_mode and c.name in {"crawl_commit", "assertive_follow"}:
                score += 0.10
            if safe_commit_window and c.name == "yield_soft":
                score -= 0.22
            if safe_commit_window and c.name == "stop_hard":
                score -= 0.45

            if moderate_risk and c.name in {"commit", "aligned_cruise", "assertive_follow"}:
                score -= 0.06
            if moderate_risk and c.name == "late_brake_keep":
                score += 0.08
            if moderate_risk and c.name == "yield_soft":
                score += 0.02

            if ped_close and c.name in {"commit", "assertive_follow", "late_brake_keep", "crawl_commit"}:
                score -= 0.45
            if ped_close and c.name in {"yield_soft", "stop_hard"}:
                score += 0.20

            scores[c.name] = score
        return scores, drives
