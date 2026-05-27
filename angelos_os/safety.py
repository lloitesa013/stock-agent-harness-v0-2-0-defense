from dataclasses import dataclass
from typing import Optional

from .schemas import CompiledProfile, GateResult, Observation


@dataclass
class SafetyConfig:
    hard_ttc: float = 0.8
    caution_ttc: float = 6.5
    handoff_ttc: float = 0.6
    front_stop_distance: float = 5.5
    front_caution_distance: float = 22.0
    ped_stop_distance: float = 5.0
    ped_caution_distance: float = 30.0
    red_light_speed_limit: float = 0.1
    low_visibility_threshold: float = 0.25
    overspeed_caution: float = 4.0


class SafetyGate:
    def __init__(self, config: Optional[SafetyConfig] = None):
        self.config = config or SafetyConfig()

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

        caution_ttc = c.caution_ttc + (1.5 if merge_mode else 0.0)
        hard_ttc = c.hard_ttc
        front_stop_distance = c.front_stop_distance + (1.0 if merge_mode else 0.0)
        front_caution_distance = c.front_caution_distance + (6.0 if merge_mode else 0.0)
        ped_stop_distance = c.ped_stop_distance + (0.5 if ped_mode else 0.0)
        ped_caution_distance = c.ped_caution_distance + (2.0 if ped_mode else 0.0)
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

        # Even at very low speed under red-light, keep the controller in a
        # strict creep-suppression mode near stop lines.
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
            throttle_scale = 0.02 if merge_mode else (0.18 if ped_mode else 0.05)
            force_brake_min = 0.6 if merge_mode else (0.38 if ped_mode else 0.45)
            if gate_bias is not None:
                throttle_scale = min(0.35, throttle_scale + max(0.0, gate_bias.degrade_throttle_bonus))
                force_brake_min = max(0.2, force_brake_min - max(0.0, gate_bias.degrade_brake_relief))
            return GateResult(
                mode="degrade",
                reason=(
                    f"merge caution mode{profile_reason_suffix}"
                    if merge_mode
                    else (
                        f"ped caution mode{profile_reason_suffix}"
                        if ped_mode
                        else f"caution mode (risk-conditioned throttle suppression){profile_reason_suffix}"
                    )
                ),
                throttle_scale=throttle_scale,
                force_brake_min=force_brake_min,
                require_human_handoff=False,
            )

        return GateResult(mode="allow", reason="normal operation")
