"""HTTP wiring for the SAIV face-recognition and risk service.

All biometric processing is local and request-scoped. This module deliberately
contains no persistence, cache, or request-body logging.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .attestation import verify_device_attestation
from .config import settings
from .detection import (
    FaceDetectionError,
    FaceDetectionResult,
    ModelUnavailableError,
    detect_face,
)
from .embedding import (
    EmbeddingModelUnavailableError,
    FaceEmbeddingError,
    NoFaceError,
    extract_face_embedding,
)
from .imaging import InvalidImageError, decode_base64_image
from .liveness import (
    LivenessUnavailableError,
    analyze_face_mesh,
    assess_liveness,
    detect_blink,
)
from .metrics import (
    record_face_outcome,
    record_liveness_outcome,
    record_risk_outcome,
    setup_metrics,
)
from .quality import assess_face_quality
from .risk import assess_risk as calculate_risk
from .risk import detect_vpn_proxy
from .schemas import (
    DeviceAttestRequest,
    DeviceAttestResponse,
    FaceEnrollRequest,
    FaceEnrollResponse,
    FaceMatchRequest,
    FaceMatchResponse,
    FaceVerifyRequest,
    FaceVerifyResponse,
    HealthResponse,
    LivenessRequest,
    LivenessResponse,
    RiskAssessRequest,
    RiskAssessResponse,
    RootResponse,
)
from .telemetry import (
    configure_privacy_logging,
    configure_telemetry,
    operation_span,
    safe_log,
    set_span_attributes,
)
from .template import (
    InvalidEmbeddingError as InvalidTemplateEmbeddingError,
    InvalidTemplateHashError,
    compare_templates,
    simhash_hex,
    validate_template_hash,
)


DISPLAY_NAME = "SAIV Face Recognition & Risk Service"
_MAX_JSON_OVERHEAD_BYTES = 128 * 1024

logger = (
    configure_privacy_logging()
    if settings.json_logging_enabled
    else logging.getLogger(settings.service_name)
)

app = FastAPI(
    title="SAIV Face Recognition Service",
    description=(
        "Face enrollment, verification, liveness detection, and risk scoring "
        "service"
    ),
    version=settings.service_version,
)


class ContentLengthLimitMiddleware:
    """Reject an obviously oversized JSON request before body parsing."""

    def __init__(self, app: Any) -> None:
        self.application = app
        encoded_image_limit = 4 * ((settings.max_image_bytes + 2) // 3)
        self.max_body_bytes = encoded_image_limit + _MAX_JSON_OVERHEAD_BYTES

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") == "http" and scope.get("method") in {
            "POST",
            "PUT",
            "PATCH",
        }:
            headers = dict(scope.get("headers") or ())
            raw_length = headers.get(b"content-length")
            if raw_length is not None:
                try:
                    content_length = int(raw_length)
                except (TypeError, ValueError):
                    response = JSONResponse(
                        status_code=400,
                        content={"detail": "Invalid Content-Length header"},
                    )
                    await response(scope, receive, send)
                    return
                if content_length < 0 or content_length > self.max_body_bytes:
                    response = JSONResponse(
                        status_code=400,
                        content={
                            "detail": "Request body exceeds the configured image limit"
                        },
                    )
                    await response(scope, receive, send)
                    return
        await self.application(scope, receive, send)


app.add_middleware(ContentLengthLimitMiddleware)
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )


@app.exception_handler(RequestValidationError)
def request_validation_error(
    _request: Request, exception: RequestValidationError
) -> JSONResponse:
    """Return useful validation metadata without echoing biometric input."""

    safe_errors = [
        {
            "type": error.get("type", "value_error"),
            "loc": list(error.get("loc", ())),
            "msg": error.get("msg", "Invalid request value"),
        }
        for error in exception.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": safe_errors})


@app.exception_handler(Exception)
def unexpected_error(_request: Request, exception: Exception) -> JSONResponse:
    """Keep native/model error details and request data out of responses/logs."""

    safe_log(
        logger,
        logging.ERROR,
        "Unhandled face-service error",
        exception_type=type(exception).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Face service could not complete the request"},
    )


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        service=settings.service_name,
        version=settings.service_version,
    )


@app.get("/", response_model=RootResponse)
def root() -> RootResponse:
    return RootResponse(
        service=DISPLAY_NAME,
        version=settings.service_version,
        endpoints=[
            "/face/enroll",
            "/face/verify",
            "/face/match",
            "/liveness/check",
            "/risk/assess",
            "/device/attest",
            "/health",
            "/metrics",
        ],
    )


def _face_processing_unavailable(exception: Exception) -> HTTPException:
    safe_log(
        logger,
        logging.ERROR,
        "Local face model unavailable",
        exception_type=type(exception).__name__,
    )
    return HTTPException(
        status_code=503,
        detail="Face processing is temporarily unavailable",
    )


def _set_detection_span(
    detection: FaceDetectionResult,
    *,
    score: float | None = None,
    passed: bool | None = None,
) -> None:
    attributes: dict[str, Any] = {
        "face.detected": detection.detected,
        "face.confidence": float(detection.confidence),
        "face.count": int(detection.face_count),
    }
    if score is not None:
        attributes["match.score"] = float(score)
    if passed is not None:
        attributes["match.passed"] = bool(passed)
    set_span_attributes(**attributes)


def generate_face_hash(embedding: Any) -> str:
    """Skeleton-compatible name for the approved cancelable SimHash template."""

    return simhash_hex(embedding)


@app.post("/face/enroll", response_model=FaceEnrollResponse, status_code=201)
def enroll_face(request: FaceEnrollRequest) -> FaceEnrollResponse:
    started = time.perf_counter()
    outcome = "error"
    image = None
    embedding = None
    with operation_span("face_enroll"):
        try:
            # Consent must be checked before decoding or inspecting the image.
            if request.camera_consent is not True:
                outcome = "invalid_input"
                raise HTTPException(
                    status_code=400,
                    detail="Camera consent is required for face enrollment",
                )

            image = decode_base64_image(request.image)
            detection = detect_face(image)
            _set_detection_span(detection)
            if (
                not detection.detected
                or detection.confidence < settings.face_detection_threshold
            ):
                outcome = "no_face"
                raise HTTPException(
                    status_code=400,
                    detail="No face detected with sufficient confidence",
                )
            if detection.multiple_faces:
                outcome = "failure"
                raise HTTPException(
                    status_code=400,
                    detail="Exactly one face is required for enrollment",
                )

            embedding = extract_face_embedding(image, detection)
            template_hash = generate_face_hash(embedding)
            quality = assess_face_quality(image, detection)
            if quality.score < settings.face_quality_threshold:
                outcome = "failure"
                raise HTTPException(
                    status_code=400,
                    detail="Face image quality is below the enrollment threshold",
                )

            outcome = "success"
            set_span_attributes(
                **{
                    "operation.outcome": outcome,
                    "operation.latency_ms": (time.perf_counter() - started) * 1000.0,
                }
            )
            return FaceEnrollResponse(
                enrollment_successful=True,
                face_template_hash=template_hash,
                quality_score=quality.score,
                details={
                    "face_detected": True,
                    "face_detection_confidence": round(
                        float(detection.confidence), 6
                    ),
                    "image_quality": quality.label,
                    "quality_components": quality.components,
                },
            )
        except InvalidImageError as exception:
            outcome = "invalid_input"
            raise HTTPException(status_code=400, detail=str(exception)) from exception
        except NoFaceError as exception:
            outcome = "no_face"
            raise HTTPException(status_code=400, detail="No face detected") from exception
        except (ModelUnavailableError, EmbeddingModelUnavailableError) as exception:
            raise _face_processing_unavailable(exception) from exception
        except (
            FaceDetectionError,
            FaceEmbeddingError,
            InvalidTemplateEmbeddingError,
        ) as exception:
            raise _face_processing_unavailable(exception) from exception
        finally:
            embedding = None
            image = None
            record_face_outcome(
                "enroll", outcome, time.perf_counter() - started
            )


def _verify_image(
    image_value: str, reference_hash: str
) -> tuple[FaceVerifyResponse, str]:
    validate_template_hash(reference_hash)
    image = None
    embedding = None
    try:
        image = decode_base64_image(image_value)
        detection = detect_face(image)
        if not detection.detected:
            _set_detection_span(detection, score=0.0, passed=False)
            return (
                FaceVerifyResponse(
                    match_passed=False,
                    match_score=0.0,
                    match_threshold=settings.face_match_threshold,
                    face_detected=False,
                    current_template_hash="",
                ),
                "no_face",
            )
        if detection.multiple_faces:
            _set_detection_span(detection, score=0.0, passed=False)
            return (
                FaceVerifyResponse(
                    match_passed=False,
                    match_score=0.0,
                    match_threshold=settings.face_match_threshold,
                    face_detected=True,
                    current_template_hash="",
                ),
                "failure",
            )

        embedding = extract_face_embedding(image, detection)
        current_hash = generate_face_hash(embedding)
        comparison = compare_templates(reference_hash, current_hash)
        response = FaceVerifyResponse(
            match_passed=comparison.match_passed,
            match_score=comparison.match_score,
            match_threshold=settings.face_match_threshold,
            face_detected=True,
            current_template_hash=current_hash,
        )
        _set_detection_span(
            detection,
            score=response.match_score,
            passed=response.match_passed,
        )
        return response, "success" if response.match_passed else "failure"
    except NoFaceError:
        negative = FaceDetectionResult(False, 0.0, None, None, 0, False)
        _set_detection_span(negative, score=0.0, passed=False)
        return (
            FaceVerifyResponse(
                match_passed=False,
                match_score=0.0,
                match_threshold=settings.face_match_threshold,
                face_detected=False,
                current_template_hash="",
            ),
            "no_face",
        )
    finally:
        embedding = None
        image = None


def _verification_endpoint(
    image_value: str,
    reference_hash: str,
    *,
    operation: str,
) -> FaceVerifyResponse:
    started = time.perf_counter()
    outcome = "error"
    with operation_span(f"face_{operation}"):
        try:
            response, outcome = _verify_image(image_value, reference_hash)
            set_span_attributes(
                **{
                    "operation.outcome": outcome,
                    "operation.latency_ms": (time.perf_counter() - started) * 1000.0,
                }
            )
            return response
        except (InvalidImageError, InvalidTemplateHashError) as exception:
            outcome = "invalid_input"
            raise HTTPException(status_code=400, detail=str(exception)) from exception
        except (ModelUnavailableError, EmbeddingModelUnavailableError) as exception:
            raise _face_processing_unavailable(exception) from exception
        except (
            FaceDetectionError,
            FaceEmbeddingError,
            InvalidTemplateEmbeddingError,
        ) as exception:
            raise _face_processing_unavailable(exception) from exception
        finally:
            record_face_outcome(operation, outcome, time.perf_counter() - started)


@app.post("/face/verify", response_model=FaceVerifyResponse)
def verify_face(request: FaceVerifyRequest) -> FaceVerifyResponse:
    return _verification_endpoint(
        request.image,
        request.reference_template_hash,
        operation="verify",
    )


@app.post("/face/match", response_model=FaceMatchResponse)
def match_face(request: FaceMatchRequest) -> FaceMatchResponse:
    verified = _verification_endpoint(
        request.image,
        request.resolved_reference_hash,
        operation="match",
    )
    return FaceMatchResponse(
        match_passed=verified.match_passed,
        match_score=verified.match_score,
        face_embedding_hash=verified.current_template_hash,
        current_template_hash=verified.current_template_hash,
        match_threshold=verified.match_threshold,
        face_detected=verified.face_detected,
    )


def _empty_liveness_details(
    confidence: float = 0.0, **extra: Any
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "face_detection_confidence": round(float(confidence), 6),
        "face_mesh_complete": False,
        "landmark_count": 0,
        "depth_detected": False,
        "depth_quality": "poor",
        "depth_score": 0.0,
        "mesh_plausibility_score": 0.0,
        "texture_analysis_score": 0.0,
        "color_distribution_score": 0.0,
        "challenge_evidence_score": 0.0,
        "challenge_integrity_score": 0.0,
        "threshold": settings.liveness_threshold,
    }
    details.update(extra)
    return details


@app.post("/liveness/check", response_model=LivenessResponse)
def check_liveness(request: LivenessRequest) -> LivenessResponse:
    started = time.perf_counter()
    outcome = "error"
    image = None
    embedding = None
    with operation_span("liveness_check"):
        try:
            image = decode_base64_image(request.challenge_response)
            detection = detect_face(image)
            if not detection.detected:
                outcome = "no_face"
                set_span_attributes(
                    **{
                        "face.detected": False,
                        "liveness.score": 0.0,
                        "liveness.passed": False,
                        "liveness.challenge_type": request.challenge_type,
                    }
                )
                return LivenessResponse(
                    liveness_passed=False,
                    liveness_score=0.0,
                    liveness_threshold=settings.liveness_threshold,
                    challenge_type=request.challenge_type,
                    face_embedding_hash="",
                    details=_empty_liveness_details(),
                )
            if detection.multiple_faces:
                outcome = "failed"
                return LivenessResponse(
                    liveness_passed=False,
                    liveness_score=0.0,
                    liveness_threshold=settings.liveness_threshold,
                    challenge_type=request.challenge_type,
                    face_embedding_hash="",
                    details=_empty_liveness_details(
                        detection.confidence,
                        multiple_faces=True,
                    ),
                )

            embedding = extract_face_embedding(image, detection)
            template_hash = generate_face_hash(embedding)
            analysis = assess_liveness(
                image,
                detection.confidence,
                detection.bbox,
                request.challenge_type,
                settings.liveness_threshold,
            )
            outcome = "passed" if analysis.liveness_passed else "failed"
            set_span_attributes(
                **{
                    "face.detected": True,
                    "face.confidence": float(detection.confidence),
                    "face.count": int(detection.face_count),
                    "liveness.score": float(analysis.liveness_score),
                    "liveness.passed": bool(analysis.liveness_passed),
                    "liveness.challenge_type": request.challenge_type,
                    "operation.outcome": outcome,
                    "operation.latency_ms": (time.perf_counter() - started) * 1000.0,
                }
            )
            return LivenessResponse(
                liveness_passed=analysis.liveness_passed,
                liveness_score=analysis.liveness_score,
                liveness_threshold=settings.liveness_threshold,
                challenge_type=request.challenge_type,
                face_embedding_hash=template_hash,
                details=analysis.details,
            )
        except InvalidImageError as exception:
            outcome = "error"
            raise HTTPException(status_code=400, detail=str(exception)) from exception
        except NoFaceError:
            outcome = "no_face"
            return LivenessResponse(
                liveness_passed=False,
                liveness_score=0.0,
                liveness_threshold=settings.liveness_threshold,
                challenge_type=request.challenge_type,
                face_embedding_hash="",
                details=_empty_liveness_details(),
            )
        except (
            ModelUnavailableError,
            EmbeddingModelUnavailableError,
            LivenessUnavailableError,
        ) as exception:
            raise _face_processing_unavailable(exception) from exception
        except (
            FaceDetectionError,
            FaceEmbeddingError,
            InvalidTemplateEmbeddingError,
        ) as exception:
            raise _face_processing_unavailable(exception) from exception
        finally:
            embedding = None
            image = None
            record_liveness_outcome(request.challenge_type, outcome)


@app.post("/risk/assess", response_model=RiskAssessResponse)
def assess_risk(request: RiskAssessRequest) -> RiskAssessResponse:
    started = time.perf_counter()
    with operation_span("risk_assess"):
        assessment = calculate_risk(
            request.model_dump(),
            risk_threshold=settings.risk_threshold,
        )
        set_span_attributes(
            **{
                "risk.score": assessment.risk_score,
                "risk.level": assessment.risk_level,
                "operation.outcome": (
                    "passed" if assessment.pass_threshold else "failed"
                ),
                "operation.latency_ms": (time.perf_counter() - started) * 1000.0,
            }
        )
        record_risk_outcome(assessment.risk_level, assessment.pass_threshold)
        return RiskAssessResponse(**assessment.as_dict())


@app.post("/device/attest", response_model=DeviceAttestResponse)
def attest_device(request: DeviceAttestRequest) -> DeviceAttestResponse:
    started = time.perf_counter()
    with operation_span("device_attest"):
        result = verify_device_attestation(request.model_dump())
        set_span_attributes(
            **{
                "operation.outcome": (
                    "success" if result.attestation_passed else "failure"
                ),
                "operation.latency_ms": (time.perf_counter() - started) * 1000.0,
            }
        )
        return DeviceAttestResponse(**result.as_dict())


# Direct exposition is required by module4-observability/prometheus.yml.
setup_metrics(app, enabled=settings.metrics_enabled)
configure_telemetry(
    app,
    service_name=settings.service_name,
    endpoint=settings.otel_exporter_otlp_endpoint,
    enabled=settings.telemetry_enabled,
)


__all__ = [
    "app",
    "health_check",
    "root",
    "enroll_face",
    "verify_face",
    "match_face",
    "check_liveness",
    "assess_risk",
    "attest_device",
    "decode_base64_image",
    "detect_face",
    "extract_face_embedding",
    "generate_face_hash",
    "analyze_face_mesh",
    "detect_blink",
    "detect_vpn_proxy",
]
