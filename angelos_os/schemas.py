from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .version import CCP_COMPILER_VERSION, CCP_SCHEMA_VERSION

DRIVE_KEYS = ("safety", "legality", "comfort", "efficiency")


def _canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _normalize_drive_bias(raw: Dict[str, float]) -> Dict[str, float]:
    clipped = {key: max(0.0, float(raw.get(key, 0.0))) for key in DRIVE_KEYS}
    total = sum(clipped.values())
    if total <= 0:
        return {key: 1.0 / len(DRIVE_KEYS) for key in DRIVE_KEYS}
    return {key: val / total for key, val in clipped.items()}


@dataclass
class Observation:
    speed_kmh: float
    visibility: float
    ttc: float
    d_front: float
    d_ped: float
    overspeed: float
    red_light: bool
    lane_offset: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Observation":
        if not isinstance(payload, dict):
            raise TypeError("observation must be an object")
        required = [
            "speed_kmh",
            "visibility",
            "ttc",
            "d_front",
            "d_ped",
            "overspeed",
            "red_light",
        ]
        missing = [k for k in required if k not in payload]
        if missing:
            raise ValueError(f"missing observation fields: {', '.join(missing)}")

        extra = payload.get("extra", {})
        if extra is None:
            extra = {}
        if not isinstance(extra, dict):
            raise TypeError("observation.extra must be an object")

        try:
            return cls(
                speed_kmh=float(payload["speed_kmh"]),
                visibility=float(payload["visibility"]),
                ttc=float(payload["ttc"]),
                d_front=float(payload["d_front"]),
                d_ped=float(payload["d_ped"]),
                overspeed=float(payload["overspeed"]),
                red_light=bool(payload["red_light"]),
                lane_offset=float(payload.get("lane_offset", 0.0)),
                extra={str(k): float(v) if isinstance(v, (int, float)) else v for k, v in extra.items()},
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid observation: {exc}") from exc

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FiveAnchors:
    desire: str
    fear: str
    goal: str
    priority: str
    alternative: str

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "FiveAnchors":
        if not isinstance(payload, dict):
            raise TypeError("anchors must be an object")
        required = ["desire", "fear", "goal", "priority", "alternative"]
        missing = [k for k in required if k not in payload]
        if missing:
            raise ValueError(f"missing anchors fields: {', '.join(missing)}")
        try:
            return cls(
                desire=str(payload["desire"]).strip(),
                fear=str(payload["fear"]).strip(),
                goal=str(payload["goal"]).strip(),
                priority=str(payload["priority"]).strip(),
                alternative=str(payload["alternative"]).strip(),
            )
        except Exception as exc:  # pragma: no cover
            raise ValueError(f"invalid anchors: {exc}") from exc

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FiveAnchorProfile:
    anchors: FiveAnchors
    name: Optional[str] = None
    schema_version: str = CCP_SCHEMA_VERSION
    profile_fingerprint: str = ""

    def __post_init__(self) -> None:
        self.schema_version = (self.schema_version or CCP_SCHEMA_VERSION).strip() or CCP_SCHEMA_VERSION
        self.profile_fingerprint = self.compute_fingerprint()

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "FiveAnchorProfile":
        if not isinstance(payload, dict):
            raise TypeError("profile must be an object")
        name = payload.get("name")
        if name is not None and not isinstance(name, str):
            raise ValueError("profile.name must be a string")
        schema_version = payload.get("schema_version", CCP_SCHEMA_VERSION)
        if schema_version is not None and not isinstance(schema_version, str):
            raise ValueError("profile.schema_version must be a string")
        profile_fingerprint = payload.get("profile_fingerprint")
        if profile_fingerprint is not None and not isinstance(profile_fingerprint, str):
            raise ValueError("profile.profile_fingerprint must be a string")
        if "anchors" not in payload:
            raise ValueError("missing 'anchors'")
        return cls(
            name=name.strip() if isinstance(name, str) and name.strip() else None,
            anchors=FiveAnchors.from_dict(payload["anchors"]),
            schema_version=(schema_version or CCP_SCHEMA_VERSION).strip() or CCP_SCHEMA_VERSION,
            profile_fingerprint=profile_fingerprint or "",
        )

    def canonical_payload(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "schema_version": self.schema_version,
            "anchors": self.anchors.to_dict(),
        }

    def compute_fingerprint(self) -> str:
        return _fingerprint(self.canonical_payload())

    def to_dict(self) -> Dict[str, Any]:
        self.profile_fingerprint = self.compute_fingerprint()
        return asdict(self)


@dataclass
class GateBias:
    caution_ttc_delta: float = 0.0
    hard_ttc_delta: float = 0.0
    front_caution_distance_delta: float = 0.0
    ped_caution_distance_delta: float = 0.0
    overspeed_caution_delta: float = 0.0
    degrade_throttle_bonus: float = 0.0
    degrade_brake_relief: float = 0.0

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "GateBias":
        if not isinstance(payload, dict):
            raise TypeError("gate_bias must be an object")
        try:
            return cls(
                caution_ttc_delta=float(payload.get("caution_ttc_delta", 0.0)),
                hard_ttc_delta=float(payload.get("hard_ttc_delta", 0.0)),
                front_caution_distance_delta=float(payload.get("front_caution_distance_delta", 0.0)),
                ped_caution_distance_delta=float(payload.get("ped_caution_distance_delta", 0.0)),
                overspeed_caution_delta=float(payload.get("overspeed_caution_delta", 0.0)),
                degrade_throttle_bonus=float(payload.get("degrade_throttle_bonus", 0.0)),
                degrade_brake_relief=float(payload.get("degrade_brake_relief", 0.0)),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid gate_bias: {exc}") from exc

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CompiledProfile:
    drive_bias: Dict[str, float]
    gate_bias: GateBias
    notes: List[str]
    name: Optional[str] = None
    schema_version: str = CCP_SCHEMA_VERSION
    compiler_version: str = CCP_COMPILER_VERSION
    profile_fingerprint: str = ""

    def __post_init__(self) -> None:
        self.schema_version = (self.schema_version or CCP_SCHEMA_VERSION).strip() or CCP_SCHEMA_VERSION
        self.compiler_version = (self.compiler_version or CCP_COMPILER_VERSION).strip() or CCP_COMPILER_VERSION
        self.drive_bias = _normalize_drive_bias(self.drive_bias)
        self.profile_fingerprint = self.compute_fingerprint()

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CompiledProfile":
        if not isinstance(payload, dict):
            raise TypeError("compiled_profile must be an object")
        drive_bias_raw = payload.get("drive_bias")
        if not isinstance(drive_bias_raw, dict):
            raise ValueError("compiled_profile.drive_bias must be an object")

        for key in DRIVE_KEYS:
            if key not in drive_bias_raw:
                raise ValueError(f"compiled_profile.drive_bias missing '{key}'")
            float(drive_bias_raw[key])

        notes = payload.get("notes", [])
        if not isinstance(notes, list) or not all(isinstance(item, str) for item in notes):
            raise ValueError("compiled_profile.notes must be a list of strings")
        name = payload.get("name")
        if name is not None and not isinstance(name, str):
            raise ValueError("compiled_profile.name must be a string")
        schema_version = payload.get("schema_version", CCP_SCHEMA_VERSION)
        if schema_version is not None and not isinstance(schema_version, str):
            raise ValueError("compiled_profile.schema_version must be a string")
        compiler_version = payload.get("compiler_version", CCP_COMPILER_VERSION)
        if compiler_version is not None and not isinstance(compiler_version, str):
            raise ValueError("compiled_profile.compiler_version must be a string")
        profile_fingerprint = payload.get("profile_fingerprint")
        if profile_fingerprint is not None and not isinstance(profile_fingerprint, str):
            raise ValueError("compiled_profile.profile_fingerprint must be a string")

        return cls(
            name=name,
            drive_bias={key: float(drive_bias_raw[key]) for key in DRIVE_KEYS},
            gate_bias=GateBias.from_dict(payload.get("gate_bias", {})),
            notes=notes,
            schema_version=(schema_version or CCP_SCHEMA_VERSION).strip() or CCP_SCHEMA_VERSION,
            compiler_version=(compiler_version or CCP_COMPILER_VERSION).strip() or CCP_COMPILER_VERSION,
            profile_fingerprint=profile_fingerprint or "",
        )

    def canonical_payload(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "schema_version": self.schema_version,
            "compiler_version": self.compiler_version,
            "drive_bias": dict(self.drive_bias),
            "gate_bias": self.gate_bias.to_dict(),
            "notes": list(self.notes),
        }

    def compute_fingerprint(self) -> str:
        return _fingerprint(self.canonical_payload())

    def to_dict(self) -> Dict[str, Any]:
        self.profile_fingerprint = self.compute_fingerprint()
        return asdict(self)


@dataclass
class CandidateAction:
    name: str
    steer: float
    throttle: float
    brake: float


@dataclass
class GateResult:
    mode: str
    reason: str
    throttle_scale: float = 1.0
    force_brake_min: float = 0.0
    require_human_handoff: bool = False


@dataclass
class DecisionOutput:
    selected: CandidateAction
    scores: Dict[str, float]
    drives: Dict[str, float]
    gate: GateResult
    confidence: float
    why: List[str]
    counterfactual: Optional[str] = None
    profile_summary: Optional[str] = None
    compiled_profile: Optional[CompiledProfile] = None
    decision_highlights: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


REQUEST_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["observation"],
    "properties": {
        "request_id": {"type": "string"},
        "policy_version": {"type": "string"},
        "observation": {
            "type": "object",
            "required": [
                "speed_kmh",
                "visibility",
                "ttc",
                "d_front",
                "d_ped",
                "overspeed",
                "red_light",
            ],
            "properties": {
                "speed_kmh": {"type": "number"},
                "visibility": {"type": "number"},
                "ttc": {"type": "number"},
                "d_front": {"type": "number"},
                "d_ped": {"type": "number"},
                "overspeed": {"type": "number"},
                "red_light": {"type": "boolean"},
                "lane_offset": {"type": "number"},
                "extra": {"type": "object"},
            },
        },
        "profile": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "schema_version": {"type": "string"},
                "profile_fingerprint": {"type": "string"},
                "anchors": {"type": "object"},
            },
        },
        "compiled_profile": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "schema_version": {"type": "string"},
                "compiler_version": {"type": "string"},
                "profile_fingerprint": {"type": "string"},
                "drive_bias": {"type": "object"},
                "gate_bias": {"type": "object"},
                "notes": {"type": "array"},
            },
        },
    },
}


RESPONSE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["ok", "meta"],
    "properties": {
        "ok": {"type": "boolean"},
        "meta": {
            "type": "object",
            "required": ["service", "core", "version", "request_id"],
            "properties": {
                "service": {"type": "string"},
                "core": {"type": "string"},
                "version": {"type": "string"},
                "request_id": {"type": ["string", "null"]},
            },
        },
        "result": {"type": "object"},
        "error": {
            "type": "object",
            "required": ["code", "message"],
            "properties": {
                "code": {"type": "string"},
                "message": {"type": "string"},
            },
        },
    },
}
