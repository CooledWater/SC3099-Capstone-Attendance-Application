"""Pydantic request and response contracts for Module 3."""

from __future__ import annotations

from numbers import Real
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    StringConstraints,
    model_validator,
)
def _require_json_number(value: Any) -> Any:
    """Reject booleans and numeric strings while still accepting JSON ints."""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("must be a JSON number")
    return value


Score = Annotated[
    float,
    BeforeValidator(_require_json_number),
    Field(ge=0.0, le=1.0, allow_inf_nan=False),
]
FiniteNumber = Annotated[
    float,
    BeforeValidator(_require_json_number),
    Field(allow_inf_nan=False),
]
NonNegativeNumber = Annotated[
    float,
    BeforeValidator(_require_json_number),
    Field(ge=0.0, allow_inf_nan=False),
]
NonEmptyString = Annotated[
    str,
    StringConstraints(strict=True, min_length=1),
]
BoundedIdentifier = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=255),
]
# Semantic 64-character/lowercase validation happens in template.py so the API
# can consistently translate every malformed reference into HTTP 400.
ReferenceHashString = StrictStr
TemplateHash = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$"),
]
TemplateHashOrEmpty = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^(?:[0-9a-f]{64})?$"),
]
ChallengeType = Literal["passive", "blink", "head_turn"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class ContractModel(BaseModel):
    """Base contract that rejects misspelled or unexpected API fields."""

    model_config = ConfigDict(extra="forbid")


class FaceEnrollRequest(ContractModel):
    """Enroll a face after explicit camera consent."""

    user_id: BoundedIdentifier
    image: NonEmptyString
    camera_consent: StrictBool


class FaceEnrollResponse(ContractModel):
    enrollment_successful: StrictBool
    face_template_hash: TemplateHash
    quality_score: Score
    details: dict[str, Any]


class FaceVerifyRequest(ContractModel):
    image: NonEmptyString
    reference_template_hash: ReferenceHashString


class FaceVerifyResponse(ContractModel):
    match_passed: StrictBool
    match_score: Score
    match_threshold: Score
    face_detected: StrictBool
    current_template_hash: TemplateHashOrEmpty


class FaceMatchRequest(ContractModel):
    """Backward-compatible matching request.

    Legacy clients send ``reference_hash`` while current clients send
    ``reference_template_hash``.  Both are accepted, but contradictory values
    are rejected instead of silently selecting one.
    """

    image: NonEmptyString
    reference_hash: ReferenceHashString | None = None
    reference_template_hash: ReferenceHashString | None = None

    @model_validator(mode="after")
    def _resolve_reference_aliases(self) -> "FaceMatchRequest":
        if self.reference_hash is None and self.reference_template_hash is None:
            raise ValueError(
                "one of reference_hash or reference_template_hash is required"
            )
        if (
            self.reference_hash is not None
            and self.reference_template_hash is not None
            and self.reference_hash != self.reference_template_hash
        ):
            raise ValueError("reference hash aliases must contain the same value")
        return self

    @property
    def resolved_reference_hash(self) -> str:
        """Return the supplied reference under either supported field name."""

        value = self.reference_template_hash or self.reference_hash
        # The model validator above guarantees this branch is unreachable, but
        # keeping the guard makes the property safe if constructed internally.
        if value is None:  # pragma: no cover - defensive invariant
            raise ValueError("reference hash is missing")
        return value


class FaceMatchResponse(ContractModel):
    """Legacy response plus current verification fields."""

    match_passed: StrictBool
    match_score: Score
    face_embedding_hash: TemplateHashOrEmpty
    current_template_hash: TemplateHashOrEmpty
    match_threshold: Score
    face_detected: StrictBool


class LivenessRequest(ContractModel):
    challenge_response: NonEmptyString
    challenge_type: ChallengeType = "passive"


class LivenessResponse(ContractModel):
    liveness_passed: StrictBool
    liveness_score: Score
    liveness_threshold: Score
    challenge_type: ChallengeType
    face_embedding_hash: TemplateHashOrEmpty
    details: dict[str, Any]


class GeolocationData(ContractModel):
    """Raw geolocation signal.

    Latitude and longitude are intentionally only checked for finiteness here.
    The risk engine must receive out-of-range coordinates so it can score them
    as maximally risky, as required by the implementation plan.
    """

    latitude: FiniteNumber
    longitude: FiniteNumber
    accuracy: NonNegativeNumber


class RiskAssessRequest(ContractModel):
    liveness_score: Score | None = None
    face_match_score: Score | None = None
    device_signature: Annotated[
        StrictStr | None,
        Field(min_length=1, max_length=16_384),
    ] = None
    device_public_key: Annotated[
        StrictStr | None,
        Field(min_length=1, max_length=32_768),
    ] = None
    ip_address: Annotated[
        StrictStr | None,
        Field(min_length=1, max_length=128),
    ] = None
    user_agent: Annotated[
        StrictStr | None,
        Field(min_length=1, max_length=2048),
    ] = None
    geolocation: GeolocationData | None = None


class RiskAssessResponse(ContractModel):
    risk_score: Score
    risk_level: RiskLevel
    pass_threshold: StrictBool
    risk_threshold: Score
    signal_breakdown: dict[str, Score]
    recommendations: list[StrictStr]


class DeviceInfo(BaseModel):
    """Device metadata included in optional attestation requests."""

    model_config = ConfigDict(extra="allow")

    platform: Annotated[StrictStr, Field(min_length=1, max_length=50)]
    os_version: Annotated[
        StrictStr | None,
        Field(min_length=1, max_length=100),
    ] = None
    device_model: Annotated[
        StrictStr | None,
        Field(min_length=1, max_length=255),
    ] = None
    app_version: Annotated[
        StrictStr | None,
        Field(min_length=1, max_length=100),
    ] = None


class DeviceAttestRequest(ContractModel):
    device_public_key: Annotated[
        StrictStr,
        Field(min_length=1, max_length=32_768),
    ]
    device_signature: Annotated[
        StrictStr,
        Field(min_length=1, max_length=16_384),
    ]
    challenge: Annotated[StrictStr, Field(min_length=1, max_length=4096)]
    device_info: DeviceInfo


class DeviceAttestResponse(ContractModel):
    attestation_passed: StrictBool
    attestation_score: Score
    device_trusted: StrictBool
    device_fingerprint: TemplateHashOrEmpty
    issues: list[StrictStr] = Field(default_factory=list)


class HealthResponse(ContractModel):
    status: Literal["healthy"]
    service: StrictStr
    version: StrictStr


class RootResponse(ContractModel):
    service: StrictStr
    version: StrictStr
    endpoints: list[StrictStr]


__all__ = [
    "Score",
    "ChallengeType",
    "RiskLevel",
    "FaceEnrollRequest",
    "FaceEnrollResponse",
    "FaceVerifyRequest",
    "FaceVerifyResponse",
    "FaceMatchRequest",
    "FaceMatchResponse",
    "LivenessRequest",
    "LivenessResponse",
    "GeolocationData",
    "RiskAssessRequest",
    "RiskAssessResponse",
    "DeviceInfo",
    "DeviceAttestRequest",
    "DeviceAttestResponse",
    "HealthResponse",
    "RootResponse",
]
