"""Opt-in, session-scoped scalar diagnostics for consented local check-in tests.

Never log request bodies, images, landmarks, templates, tokens, arbitrary error
messages or arbitrary service fields. This module does not affect decisions.
"""
import json
import logging
import math
import os
import sys
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
from inspect import signature


PREFIX = "CHECKIN_DIAGNOSTIC "
logger = logging.getLogger("saiv.checkin_diagnostics")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

_context = ContextVar("checkin_diagnostic_context", default=None)
SCORE = "score"
NUMBER = "number"
BOOL = "bool"
UUID = "uuid"
STATUS = {"approved", "flagged", "rejected", "pending", "appealed"}
COMPONENTS = {key: SCORE for key in ("depth", "mesh", "texture", "color")}
DETAILS = {
    **{key: SCORE for key in (
        "face_detection_confidence", "depth_score", "mesh_plausibility_score",
        "texture_analysis_score", "color_distribution_score", "weighted_component_score",
        "presentation_integrity_score", "challenge_evidence_score", "challenge_integrity_score",
        "threshold", "depth_threshold", "mesh_threshold", "pre_gate_liveness_score",
    )},
    "face_mesh_complete": BOOL, "depth_detected": BOOL,
    "depth_passed": BOOL, "mesh_passed": BOOL,
    "single_image_challenge_proxy": BOOL, "multiple_faces": BOOL,
    "landmark_count": NUMBER, "landmark_z_variance": NUMBER,
    "relative_nose_depth": NUMBER, "depth_quality": {"poor", "moderate", "good"},
    "weighted_contributions": COMPONENTS, "component_weights": COMPONENTS,
    "presentation_integrity_checks": {key: SCORE for key in (
        "periodicity", "texture_diversity", "color_diversity")},
    "texture_signals": {key: NUMBER for key in (
        "laplacian_variance", "sharpness_score", "luma_variance_score",
        "fft_naturalness_score", "fft_high_frequency_ratio", "fft_peak_concentration",
        "fft_peak_to_mean", "periodic_artifact_penalty", "lbp_naturalness_score",
        "lbp_entropy", "lbp_peak_fraction")},
    "color_signals": {key: SCORE for key in (
        "chroma_variance_score", "channel_spread_score", "luminance_variance_score",
        "skin_chroma_fraction", "gamut_score")},
}
SERVICE_FIELDS = {
    "liveness": {"liveness_passed": BOOL, "liveness_score": SCORE,
                 "liveness_threshold": SCORE, "challenge_type": {"passive", "blink", "head_turn"},
                 "details": DETAILS},
    "face_match": {"match_passed": BOOL, "match_score": SCORE,
                   "match_threshold": SCORE, "face_detected": BOOL},
    "module3_risk": {"risk_score": SCORE, "risk_threshold": SCORE, "pass_threshold": BOOL,
                     "risk_level": {"low", "medium", "high", "critical", "LOW", "MEDIUM", "HIGH", "CRITICAL"},
                     "signal_breakdown": {key: SCORE for key in (
                         "liveness", "face_match", "device", "network", "geolocation")}},
}
SCHEMAS = {
    "attempt_started": {},
    **{stage: {**fields, "outcome": {"received", "unavailable", "invalid_response"},
               "http_status": NUMBER} for stage, fields in SERVICE_FIELDS.items()},
    "decision": {
        "checkin_id": UUID, "status": STATUS, "risk_score": SCORE,
        "venue_risk_score": SCORE, "module3_risk_score": SCORE, "effective_threshold": SCORE,
        "distance_meters": NUMBER, "radius_meters": NUMBER, "accuracy_meters": NUMBER,
        "liveness_available": BOOL, "face_match_available": BOOL, "module3_risk_available": BOOL,
        "liveness_passed": BOOL, "liveness_score": SCORE,
        "face_match_passed": BOOL, "face_match_score": SCORE,
        "reason": {"geo_hard_reject", "liveness_failed", "risk_threshold", "below_threshold"},
    },
    "attendance_committed": {"checkin_id": UUID, "status": STATUS, "risk_score": SCORE},
    "request_failed": {"http_status": NUMBER, "reason": {"http_error", "server_error"}},
}
PATHS = {"/liveness/check": "liveness", "/face/verify": "face_match", "/risk/assess": "module3_risk"}


def _uuid(value):
    try:
        return str(uuid.UUID(value)) if isinstance(value, str) else None
    except ValueError:
        return None


def sanitize(values, schema):
    """Project onto a fixed schema; reject unexpected keys and value types."""
    if not isinstance(values, dict):
        return {}
    clean = {}
    for key, rule in schema.items():
        if key not in values:
            continue
        value = values[key]
        if isinstance(rule, dict):
            if isinstance(value, dict):
                clean[key] = sanitize(value, rule)
        elif value is None:
            clean[key] = None
        elif isinstance(rule, set):
            if isinstance(value, str) and value in rule:
                clean[key] = value
        elif rule == BOOL:
            if type(value) is bool:
                clean[key] = value
        elif rule == UUID:
            valid = _uuid(value)
            if valid:
                clean[key] = valid
        elif type(value) in (int, float):
            if math.isfinite(value) and abs(value) <= 1e12 and (rule != SCORE or 0 <= value <= 1):
                clean[key] = value
    return clean


def event(stage, **values):
    context = _context.get()
    if context is None or stage not in SCHEMAS:
        return
    try:
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), **context,
                  "stage": stage, "values": sanitize(values, SCHEMAS[stage])}
        logger.info(PREFIX + json.dumps(record, allow_nan=False, separators=(",", ":")))
    except Exception:
        # Diagnostics, including a failing log sink, must never change attendance.
        pass


@contextmanager
def capture(session_id):
    enabled = os.getenv("CHECKIN_DIAGNOSTICS_ENABLED", "false").lower() in ("true", "1", "yes")
    allowed = {_uuid(item.strip()) for item in os.getenv("CHECKIN_DIAGNOSTIC_SESSION_IDS", "").split(",")}
    sid = _uuid(session_id)
    token = _context.set({"diagnostic_id": str(uuid.uuid4()), "session_id": sid}
                         if enabled and sid is not None and sid in allowed else None)
    try:
        event("attempt_started")
        yield
    except Exception as exc:
        code = getattr(exc, "status_code", None)
        event("request_failed", http_status=code if type(code) is int else 500,
              reason="http_error" if type(code) is int else "server_error")
        raise
    finally:
        _context.reset(token)


def trace_checkin(function):
    call_signature = signature(function)

    @wraps(function)
    def wrapped(*args, **kwargs):
        payload = call_signature.bind(*args, **kwargs).arguments["checkin_data"]
        with capture(payload.session_id):
            return function(*args, **kwargs)
    return wrapped


def observe_response(path, response=None):
    """Called only on the normal service path; never reads or resends images."""
    if _context.get() is None or path not in PATHS:
        return
    stage = PATHS[path]
    try:
        if response is None:
            event(stage, outcome="unavailable")
        elif response.status_code != 200:
            event(stage, outcome="unavailable", http_status=response.status_code)
        else:
            try:
                body = response.json()
            except (ValueError, TypeError):
                body = None
            # Never forward arbitrary top-level keys through **kwargs.
            safe = sanitize(body, SERVICE_FIELDS[stage])
            event(stage, outcome="received" if isinstance(body, dict) else "invalid_response",
                  http_status=200, **safe)
    except Exception:
        pass
