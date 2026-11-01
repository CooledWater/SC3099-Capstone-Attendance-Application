"""Opt-in internal sequence measurements. Never retain pixels or landmarks."""
import math
import os
import uuid


REASONS = {"passed", "face_count", "face_jump", "identity_failed",
           "passive_first_failed", "passive_last_failed", "insufficient_blinks",
           "incomplete_blink", "identity_threshold", "invalid_images", "unavailable"}
DETAIL_SCORES = {
    "face_detection_confidence", "depth_score", "mesh_plausibility_score",
    "texture_analysis_score", "color_distribution_score", "weighted_component_score",
    "presentation_integrity_score", "challenge_evidence_score", "challenge_integrity_score",
    "threshold", "depth_threshold", "mesh_threshold", "pre_gate_liveness_score",
}
DETAIL_FLAGS = {"face_mesh_complete", "depth_detected", "depth_passed", "mesh_passed"}
DETAIL_GROUPS = {
    "weighted_contributions": {"depth", "mesh", "texture", "color"},
    "component_weights": {"depth", "mesh", "texture", "color"},
    "presentation_integrity_checks": {"periodicity", "texture_diversity", "color_diversity"},
    "texture_signals": {"periodic_artifact_penalty"},
}


def requested(headers):
    """Both services must opt in to the same session; no body/schema changes."""
    if os.getenv("CHECKIN_DIAGNOSTICS_ENABLED", "false").lower() not in ("true", "1", "yes"):
        return False
    try:
        sid = str(uuid.UUID(headers.get("X-SAIV-Diagnostic-Session-ID", "")))
    except (ValueError, TypeError, AttributeError):
        return False
    for value in os.getenv("CHECKIN_DIAGNOSTIC_SESSION_IDS", "").split(","):
        try:
            if str(uuid.UUID(value.strip())) == sid:
                return True
        except ValueError:
            continue
    return False


def _numbers(values, names, maximum=1):
    if not isinstance(values, dict):
        return {}
    return {key: value for key in names if type(value := values.get(key)) in (int, float)
            and math.isfinite(value) and 0 <= value <= maximum}


def _details(values):
    if not isinstance(values, dict):
        return {}
    clean = _numbers(values, DETAIL_SCORES)
    clean.update({key: values[key] for key in DETAIL_FLAGS if type(values.get(key)) is bool})
    for group, keys in DETAIL_GROUPS.items():
        if isinstance(values.get(group), dict):
            clean[group] = _numbers(values[group], keys)
    return clean


class SequenceDiagnostics:
    """Observer only: measurements never participate in recognition decisions."""
    def __init__(self):
        self.data = {"first_frame": {"evaluated": False}, "last_frame": {"evaluated": False},
                     "processed_frames": 0, "identity_checks": 0}

    def observe(self, stage, **values):
        if stage == "started":
            self.data.update(_numbers(values, {"frame_count", "duration_ms"}, 8000))
            self.data.update(_numbers(values, {"liveness_threshold", "depth_threshold", "mesh_threshold",
                                               "face_match_threshold"}))
            self.data.update(ear_closed_threshold=.19, ear_open_threshold=.23,
                             min_closure_ms=40, max_closure_ms=700)
        elif stage == "frame":
            self.data["processed_frames"] += 1
            self.data.update(_numbers(values, {"last_frame_index", "last_timestamp_ms"}, 8000))
        elif stage == "identity":
            self.data["identity_checks"] += 1
        elif stage == "passive" and values.get("position") in ("first_frame", "last_frame"):
            frame = {"evaluated": True, **_numbers(values, {"frame_index", "timestamp_ms"}, 8000),
                     **_numbers(values, {"liveness_score", "liveness_threshold"})}
            if type(values.get("liveness_passed")) is bool:
                frame["liveness_passed"] = values["liveness_passed"]
            frame["details"] = _details(values.get("details"))
            self.data[values["position"]] = frame
        elif stage == "finished" and values.get("reason") in REASONS:
            self.data["reason"] = values["reason"]

    def snapshot(self, reason=None):
        if reason in REASONS:
            self.data["reason"] = reason
        return self.data
