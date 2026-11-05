"""Prove privacy checks catch representative leaks, including nested JSON."""
import base64
import json
import pytest
from inspection import privacy_findings


@pytest.mark.parametrize("value", [b"\xff\xd8\xffraw", b"\x89PNG\r\n\x1a\nraw",
    base64.b64encode(b"\xff\xd8\xff" + b"x" * 40).decode(),
    {"details": json.dumps({"nested": {"image": "secret"}})},
    {"result": [{"landmarks": [1, 2, 3]}]}, {"reason": "secret-marker"}])
def test_privacy_inspector_rejects_leaks_without_echoing_them(value):
    findings = privacy_findings(value, ("secret-marker",))
    assert findings and all("secret-marker" not in finding for finding in findings)


def test_template_and_bounded_scalar_metadata_are_not_raw_images():
    assert not privacy_findings({"face_embedding_hash": "a" * 64, "liveness_score": .9, "count": 2})

