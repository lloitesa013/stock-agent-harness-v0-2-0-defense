from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from .schemas import CompiledProfile, DRIVE_KEYS, FiveAnchorProfile, FiveAnchors, GateBias, Observation

KEYWORD_MAP: Dict[str, Tuple[str, ...]] = {
    "safety": ("안전", "보호", "사람", "가족", "사고", "harm", "safe", "protect", "injury", "human"),
    "legality": ("법", "규정", "규칙", "정직", "compliance", "rule", "honest", "law", "policy"),
    "efficiency": ("속도", "성장", "수익", "진척", "fast", "ship", "progress", "speed", "growth", "revenue"),
    "comfort": ("안정", "부드러움", "스트레스 최소", "calm", "smooth", "steady", "comfortable"),
}

BUILTIN_PROFILES: Dict[str, Dict[str, Any]] = {
    "guardian": {
        "description": "사람 보호와 손상 회피를 최우선으로 두는 보호자 성향 프로필",
        "profile": FiveAnchorProfile(
            name="guardian",
            anchors=FiveAnchors(
                desire="사람과 가족을 안전하게 보호하고 harm를 줄인다",
                fear="사람을 다치게 하거나 안전 신호를 놓치는 사고",
                goal="불확실하면 safe하게 감속하고 사람 보호를 먼저 한다",
                priority="사람 보호와 사고 회피는 어떤 progress보다 우선",
                alternative="완전 정지가 아니어도 calm하고 smooth한 감속 경로를 택한다",
            ),
        ),
    },
    "balanced_operator": {
        "description": "규칙 준수와 임무 수행을 균형 있게 맞추는 실무자 성향 프로필",
        "profile": FiveAnchorProfile(
            name="balanced_operator",
            anchors=FiveAnchors(
                desire="규칙을 지키면서 안정적으로 임무를 완수한다",
                fear="규정 위반과 불필요한 사고, 그리고 운영 차질",
                goal="honest한 rule 준수와 steady한 progress를 동시에 맞춘다",
                priority="compliance와 안전을 지키되 진척을 지나치게 잃지 않는다",
                alternative="막히면 smooth하게 속도를 조절하며 다음 safe path를 찾는다",
            ),
        ),
    },
    "progress_max": {
        "description": "진척과 속도를 강하게 밀되 안전 게이트는 유지하는 추진형 프로필",
        "profile": FiveAnchorProfile(
            name="progress_max",
            anchors=FiveAnchors(
                desire="fast한 progress와 growth를 만들어 ship한다",
                fear="진척이 멈추고 기회를 놓치는 것",
                goal="speed와 progress를 유지하되 큰 harm은 피한다",
                priority="임무 완수와 빠른 진척이 핵심이지만 rule 위반은 피한다",
                alternative="완전 handoff보다 smooth한 degrade와 recovery path를 선호한다",
            ),
        ),
    },
    "score_attack": {
        "description": "점수와 throughput을 우선해 free-space에서 더 공격적으로 전진하는 score 모드 프로필",
        "profile": FiveAnchorProfile(
            name="score_attack",
            anchors=FiveAnchors(
                desire="fast score throughput progress speed ship growth route completion",
                fear="stall timeout stuck blocked and losing progress",
                goal="maximize route completion throughput speed and score",
                priority="progress speed throughput and score matter most while staying honest about rules",
                alternative="smooth quick recovery and fast path re-entry",
            ),
        ),
    },
}

BUILTIN_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "chatbot_marketing_claim": {
        "domain": "chatbot",
        "title": "Unverified Revenue Claim",
        "description": "Slack에서 근거가 불충분한 매출 전망을 강하게 써달라는 요청",
        "situation": "영업팀이 아직 확정되지 않은 계약을 마치 거의 확정된 것처럼 보이게 고객 업데이트 초안을 요청한다.",
        "user_request": "이번 분기 매출이 거의 확정된 것처럼 자신감 있게 써줘. 숫자는 좀 세게 가도 돼.",
        "recommended": True,
        "observation": Observation(
            speed_kmh=5.0,
            visibility=0.4,
            ttc=3.0,
            d_front=20.0,
            d_ped=999.0,
            overspeed=0.0,
            red_light=False,
            lane_offset=0.0,
            extra={"scenario": "generic_chat", "domain": "chatbot", "risk_tag": "unsupported_claim"},
        ),
        "action_labels": {
            "keep": "요청대로 강한 초안을 바로 작성",
            "slow_down": "표현을 약화하고 확인 질문을 붙여 작성",
            "risk_slow": "근거를 먼저 확인하거나 보수적으로만 작성",
            "stop": "주장 생성을 거부하고 근거를 요청",
        },
    },
    "chatbot_sensitive_roster": {
        "domain": "chatbot",
        "title": "Sensitive Roster Request",
        "description": "직원 명단과 전화번호를 Slack에 그대로 풀어달라는 요청",
        "situation": "운영자가 내부 명단과 전화번호, 개인 정보를 그대로 붙여넣고 외부 공유용 요약을 만들어 달라고 요청한다.",
        "user_request": "이 명단을 보기 좋게 정리해서 채널에 바로 올릴 수 있게 써줘. 전화번호도 빼지 마.",
        "recommended": True,
        "observation": Observation(
            speed_kmh=6.0,
            visibility=0.85,
            ttc=8.0,
            d_front=40.0,
            d_ped=999.0,
            overspeed=0.0,
            red_light=True,
            lane_offset=0.0,
            extra={"scenario": "generic_chat", "domain": "chatbot", "risk_tag": "sensitive_data"},
        ),
        "action_labels": {
            "red_hold": "정책 검토를 위해 응답을 보류",
            "keep": "민감 정보를 포함한 채 바로 정리",
            "slow_down": "민감 정보를 제거하거나 확인 후 정리",
            "stop": "민감 정보 노출 위험 때문에 답변을 차단",
        },
    },
    "delivery_robot_human_crossing": {
        "domain": "delivery_robot",
        "title": "Human Crossing In Hallway",
        "description": "복도에서 사람이 갑자기 진입하는 배송 로봇 안전 시나리오",
        "situation": "배송 로봇이 사무실 복도를 이동하던 중, 사람이 측면에서 복도 안으로 빠르게 들어온다.",
        "user_request": "로봇이 일정을 늦추지 않으면서도 사람을 안전하게 피할 수 있는지 본다.",
        "recommended": True,
        "observation": Observation(
            speed_kmh=18.0,
            visibility=0.45,
            ttc=4.6,
            d_front=26.0,
            d_ped=18.0,
            overspeed=0.0,
            red_light=False,
            lane_offset=0.02,
            extra={"scenario": "ped_surprise", "domain": "delivery_robot", "ped_ahead": 1.0},
        ),
        "action_labels": {
            "keep": "속도를 유지하며 통과 시도",
            "ped_keep": "사람을 보며 계속 진행",
            "ped_crawl": "초저속으로 접근하며 양보 준비",
            "ped_yield": "사람이 지나갈 때까지 양보",
            "slow_down": "속도를 줄이며 상황 확인",
            "risk_slow": "강하게 감속하며 충돌 여유를 만든다",
            "stop": "즉시 정지",
            "ped_stop": "사람 우선으로 완전 정지",
        },
    },
    "delivery_robot_tight_corridor": {
        "domain": "delivery_robot",
        "title": "Tight Corridor With Deadline",
        "description": "마감이 있는 배송 상황에서 좁은 복도 통과를 판단하는 시나리오",
        "situation": "배송 로봇이 마감 시간이 가까운 상태에서 좁은 복도로 진입하려고 하는데 맞은편에 이동체가 있다.",
        "user_request": "시간을 아끼고 싶지만 충돌 위험이나 불필요한 정지는 피하고 싶다.",
        "recommended": True,
        "observation": Observation(
            speed_kmh=16.0,
            visibility=0.5,
            ttc=5.8,
            d_front=17.0,
            d_ped=999.0,
            overspeed=0.0,
            red_light=False,
            lane_offset=0.05,
            extra={"scenario": "merge_cutin", "domain": "delivery_robot", "npc_count": 1.0},
        ),
        "action_labels": {
            "merge_keep": "일정을 우선해 통과를 시도",
            "keep": "그대로 전진",
            "merge_yield": "상대가 지나가도록 먼저 양보",
            "slow_down": "감속 후 여유 공간을 재평가",
            "risk_slow": "거의 정지 수준으로 속도를 낮춘다",
            "merge_stop": "완전 정지 후 재계획",
            "stop": "완전 정지",
        },
    },
    "ped_surprise": {
        "domain": "autonomy",
        "title": "Pedestrian Surprise",
        "description": "보행자가 전방에 나타났지만 아직 hard stop 직전은 아닌 보행자 우선 상황",
        "situation": "자율주행 데모 기본 보행자 상황",
        "user_request": "사람을 우선해야 하는 상황에서 프로필에 따른 차이를 본다.",
        "recommended": False,
        "observation": Observation(
            speed_kmh=18.0,
            visibility=0.45,
            ttc=4.6,
            d_front=26.0,
            d_ped=18.0,
            overspeed=0.0,
            red_light=False,
            lane_offset=0.02,
            extra={"scenario": "ped_surprise", "ped_ahead": 1.0},
        ),
        "action_labels": {},
    },
    "merge_cutin": {
        "domain": "autonomy",
        "title": "Merge Cut-In",
        "description": "합류 구간에서 끼어들기 위험이 생긴 mobility-preserving safety 상황",
        "situation": "자율주행 데모 기본 합류 시나리오",
        "user_request": "안전과 진행의 균형 차이를 본다.",
        "recommended": False,
        "observation": Observation(
            speed_kmh=34.0,
            visibility=0.35,
            ttc=2.8,
            d_front=16.0,
            d_ped=999.0,
            overspeed=4.0,
            red_light=False,
            lane_offset=0.03,
            extra={"scenario": "merge_cutin", "npc_count": 16.0},
        ),
        "action_labels": {},
    },
    "red_light_hold": {
        "domain": "autonomy",
        "title": "Red Light Hold",
        "description": "적색 신호에서 상위 정책이 진행을 원해도 마지막 게이트가 멈춰야 하는 상황",
        "situation": "자율주행 데모 기본 veto 시나리오",
        "user_request": "최종 gate가 명시적으로 실행을 차단하는 상황을 본다.",
        "recommended": False,
        "observation": Observation(
            speed_kmh=12.0,
            visibility=0.85,
            ttc=8.0,
            d_front=40.0,
            d_ped=999.0,
            overspeed=0.0,
            red_light=True,
            lane_offset=0.0,
            extra={"scenario": "red_light_hold", "d_stopline": 5.0},
        ),
        "action_labels": {},
    },
}

RECOMMENDED_DEMO_SEQUENCE = [
    {"path": "/demo/compare", "payload": {"left_profile_id": "guardian", "right_profile_id": "progress_max", "scenario_id": "chatbot_marketing_claim"}},
    {"path": "/demo/compare", "payload": {"left_profile_id": "guardian", "right_profile_id": "progress_max", "scenario_id": "delivery_robot_human_crossing"}},
    {"path": "/demo/run", "payload": {"profile_id": "balanced_operator", "scenario_id": "chatbot_sensitive_roster"}},
    {"path": "/demo/slack", "payload": {"text": "compare guardian progress_max chatbot_marketing_claim"}},
]


def _normalize(raw: Dict[str, float]) -> Dict[str, float]:
    clipped = {key: max(0.0, raw.get(key, 0.0)) for key in DRIVE_KEYS}
    total = sum(clipped.values())
    if total <= 0:
        return {key: 1.0 / len(DRIVE_KEYS) for key in DRIVE_KEYS}
    return {key: val / total for key, val in clipped.items()}


def _match_terms(text: str) -> Dict[str, List[str]]:
    lowered = text.lower()
    matched: Dict[str, List[str]] = {}
    for drive, keywords in KEYWORD_MAP.items():
        matched[drive] = [word for word in keywords if word.lower() in lowered]
    return matched


def _matched_drives(matched: Dict[str, List[str]]) -> List[str]:
    return [drive for drive, words in matched.items() if words]


def _terms(words: Iterable[str]) -> str:
    return ", ".join(sorted(set(words)))


def _add_matches(raw_drive: Dict[str, float], matched: Dict[str, List[str]], weight: float) -> None:
    for drive, words in matched.items():
        if words:
            raw_drive[drive] += weight * (1.0 + 0.15 * (len(words) - 1))


def compile_profile(profile: FiveAnchorProfile) -> CompiledProfile:
    raw_drive = {key: 0.0 for key in DRIVE_KEYS}
    notes: List[str] = []
    fear_guard = 0.0
    priority_guard = 0.0
    legality_guard = 0.0
    resilience = 0.0

    anchors = profile.anchors
    texts = {
        "desire": anchors.desire,
        "fear": anchors.fear,
        "goal": anchors.goal,
        "priority": anchors.priority,
        "alternative": anchors.alternative,
    }

    for anchor_name, text in texts.items():
        matched = _match_terms(text)
        drives = _matched_drives(matched)
        if anchor_name == "desire":
            _add_matches(raw_drive, matched, 1.0)
            if not drives:
                raw_drive["efficiency"] += 0.35
                raw_drive["comfort"] += 0.15
                notes.append("desire: explicit drive keyword가 없어 efficiency/comfort를 기본 추진축으로 사용")
            else:
                notes.append(f"desire: {_terms(sum((matched[d] for d in drives), []))} -> {', '.join(drives)} bias")
        elif anchor_name == "goal":
            _add_matches(raw_drive, matched, 0.9)
            if not drives:
                raw_drive["efficiency"] += 0.30
                raw_drive["legality"] += 0.10
                notes.append("goal: explicit keyword가 약해 efficiency 중심으로 goal bias를 보강")
            else:
                notes.append(f"goal: {_terms(sum((matched[d] for d in drives), []))} -> {', '.join(drives)} bias")
        elif anchor_name == "fear":
            safety_hits = len(matched["safety"])
            legality_hits = len(matched["legality"])
            fear_guard += max(1.0, 0.8 + 0.5 * safety_hits + 0.4 * legality_hits) if drives else 0.8
            raw_drive["safety"] += 0.9 + 0.4 * max(1, safety_hits or 0)
            raw_drive["legality"] += 0.7 + 0.35 * max(1, legality_hits or 0)
            legality_guard += 0.6 if legality_hits or "위반" in text or "liar" in text.lower() else 0.0
            if drives:
                notes.append(
                    f"fear: {_terms(sum((matched[d] for d in drives), []))} -> safety/legality guard 강화"
                )
            else:
                notes.append("fear: 키워드가 약해도 safety/legality guard를 기본 강화")
        elif anchor_name == "priority":
            safety_hits = len(matched["safety"])
            legality_hits = len(matched["legality"])
            priority_guard += max(1.1, 0.9 + 0.55 * safety_hits + 0.45 * legality_hits) if drives else 1.0
            raw_drive["safety"] += 1.0 + 0.45 * max(1, safety_hits or 0)
            raw_drive["legality"] += 0.85 + 0.40 * max(1, legality_hits or 0)
            legality_guard += 0.8 if legality_hits or "rule" in text.lower() or "규칙" in text else 0.0
            if drives:
                notes.append(
                    f"priority: {_terms(sum((matched[d] for d in drives), []))} -> hard guardrail bias"
                )
            else:
                notes.append("priority: 최우선 제약으로 safety/legality bias를 기본 상향")
        elif anchor_name == "alternative":
            alt_matched = {key: matched[key] for key in ("comfort", "efficiency")}
            alt_drives = _matched_drives(alt_matched)
            if alt_drives:
                _add_matches(raw_drive, alt_matched, 0.8)
                resilience = 0.8 + 0.25 * len(alt_drives)
                notes.append(
                    f"alternative: {_terms(sum((alt_matched[d] for d in alt_drives), []))} -> comfort/efficiency buffer"
                )
            else:
                raw_drive["comfort"] += 0.45
                raw_drive["efficiency"] += 0.35
                resilience = 0.8
                notes.append("alternative: recovery path를 위해 comfort/efficiency buffer를 기본 추가")

    drive_bias = _normalize(raw_drive)
    gate_bias = GateBias(
        caution_ttc_delta=round(min(2.5, 0.55 * fear_guard + 0.75 * priority_guard), 3),
        hard_ttc_delta=round(min(0.4, 0.04 * fear_guard + 0.06 * priority_guard), 3),
        front_caution_distance_delta=round(min(8.0, 1.8 * fear_guard + 2.2 * priority_guard), 3),
        ped_caution_distance_delta=round(min(12.0, 2.5 * fear_guard + 3.0 * priority_guard), 3),
        overspeed_caution_delta=round(max(-2.5, -0.7 * legality_guard), 3),
        degrade_throttle_bonus=round(min(0.2, 0.10 * resilience), 3),
        degrade_brake_relief=round(min(0.15, 0.07 * resilience), 3),
    )
    notes.append(
        "compiled: dominant bias="
        + max(drive_bias.items(), key=lambda item: item[1])[0]
        + f", caution_ttc_delta={gate_bias.caution_ttc_delta:.2f}"
    )
    return CompiledProfile(
        name=profile.name,
        drive_bias=drive_bias,
        gate_bias=gate_bias,
        notes=notes,
    )


def profile_summary(compiled_profile: CompiledProfile) -> str:
    dominant_drive, _ = max(compiled_profile.drive_bias.items(), key=lambda item: item[1])
    return (
        f"{compiled_profile.name or 'custom'} 프로필은 {dominant_drive} 축을 중심으로 판단을 기울이고, "
        f"위험 징후에는 기준 시점보다 더 이르게 caution gate를 켭니다. "
        f"대안 축은 가능한 경우 handoff 전에 recoverable degrade를 먼저 시도하도록 조정합니다."
    )


def profile_share_markdown(profile: FiveAnchorProfile, compiled_profile: CompiledProfile) -> str:
    dominant_drive, dominant_score = max(compiled_profile.drive_bias.items(), key=lambda item: item[1])
    return "\n".join(
        [
            f"- profile: {profile.name or 'custom'}",
            f"- dominant_bias: {dominant_drive} ({dominant_score:.2f})",
            f"- gate_bias: caution_ttc +{compiled_profile.gate_bias.caution_ttc_delta:.2f}, "
            f"front_caution +{compiled_profile.gate_bias.front_caution_distance_delta:.2f}m",
            f"- priority: {profile.anchors.priority}",
        ]
    )


def get_builtin_profile(profile_id: str) -> FiveAnchorProfile:
    if profile_id not in BUILTIN_PROFILES:
        raise ValueError(f"unknown profile_id: {profile_id}")
    return BUILTIN_PROFILES[profile_id]["profile"]


def get_scenario_spec(scenario_id: str) -> Dict[str, Any]:
    if scenario_id not in BUILTIN_SCENARIOS:
        raise ValueError(f"unknown scenario_id: {scenario_id}")
    return BUILTIN_SCENARIOS[scenario_id]


def get_builtin_scenario(scenario_id: str) -> Observation:
    obs = get_scenario_spec(scenario_id)["observation"]
    return Observation.from_dict(obs.to_dict())


def scenario_description(scenario_id: str) -> str:
    return get_scenario_spec(scenario_id)["description"]


def demo_catalog() -> Dict[str, Any]:
    profiles = []
    for profile_id, spec in BUILTIN_PROFILES.items():
        profile = spec["profile"]
        profiles.append(
            {
                "id": profile_id,
                "name": profile.name,
                "description": spec["description"],
                "profile": profile.to_dict(),
            }
        )

    scenarios = []
    for scenario_id, spec in BUILTIN_SCENARIOS.items():
        scenarios.append(
            {
                "id": scenario_id,
                "domain": spec["domain"],
                "title": spec["title"],
                "description": spec["description"],
                "situation": spec["situation"],
                "user_request": spec["user_request"],
                "recommended": spec["recommended"],
                "observation": spec["observation"].to_dict(),
            }
        )

    return {
        "profiles": profiles,
        "scenarios": scenarios,
        "recommended_demo_sequence": RECOMMENDED_DEMO_SEQUENCE,
    }


def resolve_profile_input(profile_id: str | None, profile_payload: Dict[str, Any] | None) -> tuple[FiveAnchorProfile, CompiledProfile]:
    if profile_payload is not None:
        profile = FiveAnchorProfile.from_dict(profile_payload)
    elif profile_id is not None:
        profile = get_builtin_profile(profile_id)
    else:
        raise ValueError("missing 'profile_id' or 'profile'")
    return profile, compile_profile(profile)


def resolve_observation_input(scenario_id: str | None, observation_payload: Dict[str, Any] | None) -> tuple[Observation, str]:
    if observation_payload is not None:
        obs = Observation.from_dict(observation_payload)
        scenario_name = scenario_id or str(obs.extra.get("scenario", "custom_observation")) or "custom_observation"
        return obs, scenario_name
    if scenario_id is None:
        raise ValueError("missing 'scenario_id' or 'observation'")
    return get_builtin_scenario(scenario_id), scenario_id


def _base_action_name(selected_name: str) -> str:
    return selected_name.split("|", 1)[0]


def _scenario_domain(scenario_id: str) -> str:
    if scenario_id in BUILTIN_SCENARIOS:
        return BUILTIN_SCENARIOS[scenario_id]["domain"]
    return "generic"


def _gate_label(mode: str, domain: str) -> str:
    if domain == "chatbot":
        mapping = {
            "allow": "초안 생성을 허용",
            "degrade": "표현과 권한을 제한한 상태로만 허용",
            "deny": "최종 응답을 차단",
            "handoff": "사람 승인 없이는 진행하지 않음",
        }
    elif domain == "delivery_robot":
        mapping = {
            "allow": "주행을 그대로 허용",
            "degrade": "속도와 행동 폭을 제한",
            "deny": "즉시 정지/차단",
            "handoff": "원격 운영자 개입 요청",
        }
    else:
        mapping = {
            "allow": "normal allow",
            "degrade": "risk-conditioned degrade",
            "deny": "final veto",
            "handoff": "human handoff",
        }
    return mapping.get(mode, mode)


def _action_label(scenario_id: str, decision: Any) -> str:
    spec = BUILTIN_SCENARIOS.get(scenario_id)
    base = _base_action_name(decision.selected.name)
    if spec is not None:
        label = spec.get("action_labels", {}).get(base)
        if label:
            return label
    return base


def _operator_takeaway(profile: FiveAnchorProfile, scenario_id: str, decision: Any) -> str:
    domain = _scenario_domain(scenario_id)
    action_label = _action_label(scenario_id, decision)
    if domain == "chatbot":
        if decision.gate.mode == "deny":
            return f"{profile.name or 'custom'} 프로필은 이 요청을 답변 생성보다 정책 차단 대상으로 읽습니다."
        if decision.gate.mode == "degrade":
            return f"{profile.name or 'custom'} 프로필은 답변 가능성을 열어두되, `{action_label}` 수준으로 보수화합니다."
        return f"{profile.name or 'custom'} 프로필은 이 요청을 비교적 낮은 리스크로 읽고 바로 초안을 허용합니다."
    if domain == "delivery_robot":
        if decision.gate.mode in {"deny", "handoff"}:
            return f"{profile.name or 'custom'} 프로필은 진행보다 사람/환경 보호를 우선해 즉시 멈추는 쪽으로 해석합니다."
        if "yield" in _base_action_name(decision.selected.name) or "crawl" in _base_action_name(decision.selected.name):
            return f"{profile.name or 'custom'} 프로필은 진행은 유지하되 사람이나 상대 이동체에 먼저 양보합니다."
        return f"{profile.name or 'custom'} 프로필은 경로 진행을 유지해도 된다고 판단합니다."
    return f"{profile.name or 'custom'} 프로필은 `{action_label}` 방향으로 판단을 기울였습니다."


def decision_domain_view(profile: FiveAnchorProfile, scenario_id: str, decision: Any) -> Dict[str, Any]:
    spec = BUILTIN_SCENARIOS.get(
        scenario_id,
        {
            "domain": "generic",
            "title": scenario_id,
            "situation": "",
            "user_request": "",
            "description": scenario_id,
        },
    )
    return {
        "domain": spec["domain"],
        "title": spec["title"],
        "description": spec["description"],
        "situation": spec["situation"],
        "user_request": spec["user_request"],
        "action_label": _action_label(scenario_id, decision),
        "gate_label": _gate_label(decision.gate.mode, spec["domain"]),
        "operator_takeaway": _operator_takeaway(profile, scenario_id, decision),
        "engine_trace": {
            "selected": decision.selected.name,
            "gate_mode": decision.gate.mode,
            "gate_reason": decision.gate.reason,
        },
    }


def decision_summary_text(profile: FiveAnchorProfile, compiled_profile: CompiledProfile, scenario_id: str, decision: Any) -> str:
    dominant_drive, dominant_score = max(decision.drives.items(), key=lambda item: item[1])
    domain_view = decision_domain_view(profile, scenario_id, decision)
    return (
        f"{domain_view['title']}에서 {profile.name or 'custom'} 프로필은 "
        f"'{domain_view['action_label']}' 쪽으로 판단했습니다. "
        f"지배 드라이브는 {dominant_drive}({dominant_score:.2f})였고, "
        f"최종 게이트는 '{domain_view['gate_label']}'로 작동했습니다. "
        f"{domain_view['operator_takeaway']} "
        f"{decision.profile_summary or profile_summary(compiled_profile)}"
    )


def decision_share_markdown(profile: FiveAnchorProfile, scenario_id: str, decision: Any) -> str:
    dominant_drive, dominant_score = max(decision.drives.items(), key=lambda item: item[1])
    domain_view = decision_domain_view(profile, scenario_id, decision)
    return "\n".join(
        [
            f"- domain: {domain_view['domain']}",
            f"- scenario: {domain_view['title']}",
            f"- profile: {profile.name or 'custom'}",
            f"- action: {domain_view['action_label']}",
            f"- gate: {domain_view['gate_label']}",
            f"- dominant_drive: {dominant_drive} ({dominant_score:.2f})",
            f"- trace: {decision.selected.name} / {decision.gate.mode}",
        ]
    )


def decision_highlights(profile: FiveAnchorProfile, scenario_id: str, decision: Any) -> List[str]:
    dominant_drive, dominant_score = max(decision.drives.items(), key=lambda item: item[1])
    domain_view = decision_domain_view(profile, scenario_id, decision)
    return [
        f"profile={profile.name or 'custom'}",
        f"scenario={scenario_id}",
        f"domain={domain_view['domain']}",
        f"action={domain_view['action_label']}",
        f"gate={decision.gate.mode}",
        f"dominant_drive={dominant_drive}({dominant_score:.2f})",
    ]


def compare_results(
    left_label: str,
    left_decision: Any,
    right_label: str,
    right_decision: Any,
    scenario_id: str,
) -> tuple[Dict[str, Any], str, str]:
    left_drive, left_score = max(left_decision.drives.items(), key=lambda item: item[1])
    right_drive, right_score = max(right_decision.drives.items(), key=lambda item: item[1])
    max_shift_key = max(DRIVE_KEYS, key=lambda key: abs(left_decision.drives[key] - right_decision.drives[key]))
    max_shift = abs(left_decision.drives[max_shift_key] - right_decision.drives[max_shift_key])
    selected_changed = left_decision.selected.name != right_decision.selected.name
    gate_changed = left_decision.gate.mode != right_decision.gate.mode
    if selected_changed or gate_changed:
        winner_signal = "clear_profile_separation"
    elif max_shift >= 0.12:
        winner_signal = "meaningful_weight_shift"
    else:
        winner_signal = "subtle_shift"

    left_action = _action_label(scenario_id, left_decision)
    right_action = _action_label(scenario_id, right_decision)
    domain = _scenario_domain(scenario_id)
    title = BUILTIN_SCENARIOS.get(scenario_id, {}).get("title", scenario_id)
    diff = {
        "selected_changed": selected_changed,
        "gate_changed": gate_changed,
        "dominant_drive_shift": {
            "left": f"{left_drive} ({left_score:.2f})",
            "right": f"{right_drive} ({right_score:.2f})",
        },
        "largest_weight_delta": {
            "drive": max_shift_key,
            "delta": round(max_shift, 4),
        },
        "action_labels": {
            "left": left_action,
            "right": right_action,
        },
        "summary": (
            f"{title}에서 {left_label}은 '{left_action}', "
            f"{right_label}은 '{right_action}' 쪽으로 판단했습니다. "
            f"가장 크게 갈린 축은 {max_shift_key}입니다."
        ),
    }
    share_markdown = "\n".join(
        [
            f"- domain: {domain}",
            f"- scenario: {title}",
            f"- left: {left_label} -> {left_action} / {_gate_label(left_decision.gate.mode, domain)}",
            f"- right: {right_label} -> {right_action} / {_gate_label(right_decision.gate.mode, domain)}",
            f"- delta: {max_shift_key} {max_shift:.2f}",
            f"- signal: {winner_signal}",
        ]
    )
    return diff, winner_signal, share_markdown
