"""Check that missing, unconfirmed and malformed physical evidence fails clearly."""
import json
import pytest
from corpus import load_cases


@pytest.fixture
def manifest(tmp_path):
    # Only parser fixtures; these are never used as physical ML evidence.
    (tmp_path / "enroll.jpg").write_bytes(b"parser-fixture")
    (tmp_path / "capture.jpg").write_bytes(b"parser-fixture")
    data = {"version": 1, "subjects": [{"id": "subject", "consent_confirmed": True, "enrollment": "enroll.jpg", "captures": [
        {"id": "capture", "kind": "print", "presentation_confirmed": True, "image": "capture.jpg"}]}]}
    return tmp_path / "manifest.json", data


@pytest.mark.parametrize("fault", ["consent", "presentation", "duplicate", "same_capture", "missing_file", "unknown_kind", "video_without_frames", "url"])
def test_bad_corpus_cannot_be_counted_as_real_attack_coverage(manifest, fault):
    path, data = manifest
    subject = data["subjects"][0]; capture = subject["captures"][0]
    if fault == "consent": subject["consent_confirmed"] = False
    elif fault == "presentation": capture["presentation_confirmed"] = False
    elif fault == "duplicate": data["subjects"].append(subject.copy())
    elif fault == "same_capture": capture["image"] = subject["enrollment"]
    elif fault == "missing_file": capture["image"] = "absent.jpg"
    elif fault == "unknown_kind": capture["kind"] = "synthetic"
    elif fault == "video_without_frames": capture["kind"] = "screen_video"
    elif fault == "url": capture["image"] = "https://example.org/capture.jpg"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_cases(path)


def test_confirmed_local_corpus_loads_metadata_without_image_bytes(manifest):
    path, data = manifest
    path.write_text(json.dumps(data))
    cases = load_cases(path)
    assert len(cases) == 1 and cases[0]["kind"] == "print"
    assert cases[0]["image"].endswith("capture.jpg")
    assert "parser-fixture" not in json.dumps(cases)

