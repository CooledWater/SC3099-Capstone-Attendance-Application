"""Strict loader for operator-labelled, consented real capture datasets."""
from __future__ import annotations
import base64
import json
from pathlib import Path


def load_cases(filename):
    path = Path(filename).expanduser().resolve()
    data = json.loads(path.read_text())
    if data.get("version") != 1 or not isinstance(data.get("subjects"), list) or not data["subjects"]:
        raise ValueError("Corpus requires version=1 and a nonempty subjects array")
    cases, identities = [], set()
    def source(value):
        if not isinstance(value, str) or not value or "://" in value:
            raise ValueError("Capture paths must be local image paths")
        candidate = (path.parent / value).resolve()
        if not candidate.is_file() or candidate.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            raise ValueError("Capture file missing or unsupported: " + candidate.name)
        if candidate.stat().st_size > 8 * 1024 * 1024:
            raise ValueError("Capture exceeds 8 MiB")
        return str(candidate)
    for subject in data["subjects"]:
        identity = subject.get("id")
        if not isinstance(identity, str) or not identity or identity in identities:
            raise ValueError("Subjects require unique nonempty IDs")
        identities.add(identity)
        if subject.get("consent_confirmed") is not True:
            raise ValueError("Every subject requires consent_confirmed=true")
        enrollment = source(subject["enrollment"])
        captures = subject.get("captures")
        if not isinstance(captures, list) or not captures:
            raise ValueError("Every subject requires labelled captures")
        capture_ids = set()
        for capture in captures:
            name = capture.get("id")
            if not isinstance(name, str) or not name or name in capture_ids:
                raise ValueError("Capture IDs must be unique per subject")
            capture_ids.add(name)
            if capture.get("presentation_confirmed") is not True:
                raise ValueError("Session names alone are insufficient; confirm actual physical presentations")
            kind = capture.get("kind")
            if kind not in {"genuine", "impostor", "print", "screen_photo", "screen_video", "genuine_sequence", "deepfake", "mask"}:
                raise ValueError("Unsupported physical capture kind")
            case = dict(id=identity + "/" + name, kind=kind, enrollment=enrollment)
            if "frames" in capture:
                raw_frames = capture["frames"]
                if not isinstance(raw_frames, list) or not 15 <= len(raw_frames) <= 120:
                    raise ValueError("Sequence requires 15..120 frames")
                case["frames"] = [{"image_path": source(frame["image"]), "timestamp_ms": frame["timestamp_ms"]} for frame in raw_frames]
                times = [frame["timestamp_ms"] for frame in case["frames"]]
                if any(type(value) is not int or not 0 <= value <= 8000 for value in times):
                    raise ValueError("Frame timestamps must be JSON integers within 0..8000 ms")
                if times[0] > 250 or times[-1] - times[0] < 1000 or any(not 0 < b-a <= 250 for a,b in zip(times,times[1:])):
                    raise ValueError("Sequence timing does not satisfy the API capture contract")
                spec = capture.get("challenge")
                if not isinstance(spec, dict) or set(spec) != {"version", "blink_target", "turn_direction", "first_action"}:
                    raise ValueError("Every sequence must identify the challenge actually performed")
                if type(spec["version"]) is not int or spec["version"] != 2 or type(spec["blink_target"]) is not int or spec["blink_target"] not in (1,2) or spec["turn_direction"] not in ("left","right") or spec["first_action"] not in ("blink","head_turn"):
                    raise ValueError("Invalid version-2 challenge descriptor")
                case["challenge"] = spec
            else:
                if kind in {"screen_video", "genuine_sequence"}:
                    raise ValueError("Video/sequence labels require actual frame sequences")
                case["image"] = source(capture["image"])
                if case["image"] == enrollment:
                    raise ValueError("Use a held-out capture rather than the enrollment file")
            cases.append(case)
    return cases


def encoded_file(filename):
    return base64.b64encode(Path(filename).read_bytes()).decode("ascii")


def sequence_payload(case, reference):
    values = [{"image": encoded_file(frame["image_path"]), "timestamp_ms": frame["timestamp_ms"]} for frame in case["frames"]]
    if any(len(value["image"]) > 100000 for value in values) or sum(len(value["image"]) for value in values) > 6000000:
        raise ValueError("Captured sequence exceeds API image budgets; prepare suitable captures before evaluation")
    return {"frames": values, "challenge": case["challenge"], "reference_template_hash": reference}

