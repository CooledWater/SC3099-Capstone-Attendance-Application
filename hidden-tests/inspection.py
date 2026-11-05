"""Privacy inspectors return locations only, never leaked values."""
from __future__ import annotations
import base64
import binascii
import json
import re

IMAGE_MAGIC = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF87a", b"GIF89a", b"RIFF")
RAW_KEYS = {"image", "image_data", "face_image", "raw_image", "photo", "raw_embedding", "embedding", "landmarks", "frames"}


def privacy_findings(value, forbidden=(), location="value"):
    findings = []
    if isinstance(value, (bytes, bytearray, memoryview)):
        value = bytes(value)
        if value.startswith(IMAGE_MAGIC):
            findings.append(location + ": image bytes")
        if any(isinstance(item, bytes) and item and item in value for item in forbidden):
            findings.append(location + ": submitted bytes")
        return findings
    if isinstance(value, dict):
        for key, item in value.items():
            path = location + "." + str(key)
            if str(key).lower() in RAW_KEYS and item is not None:
                findings.append(path + ": raw biometric field")
            findings.extend(privacy_findings(item, forbidden, path))
        return findings
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            findings.extend(privacy_findings(item, forbidden, f"{location}[{index}]"))
        return findings
    if not isinstance(value, str):
        return findings
    if any(isinstance(item, str) and item and item in value for item in forbidden):
        findings.append(location + ": submitted secret/image")
    stripped = value.strip()
    if stripped[:1] in ("{", "["):
        try:
            decoded = json.loads(stripped)
        except (ValueError, TypeError):
            pass
        else:
            findings.extend(privacy_findings(decoded, forbidden, location + ".json"))
    candidate = stripped.split(",", 1)[-1] if stripped.startswith("data:image/") else stripped
    if len(candidate) >= 16 and re.fullmatch(r"[A-Za-z0-9+/=\r\n]+", candidate):
        try:
            # Only the prefix is needed to identify common file formats.
            prefix = base64.b64decode(candidate[:128], validate=False)
        except (binascii.Error, ValueError):
            pass
        else:
            if prefix.startswith(IMAGE_MAGIC):
                findings.append(location + ": encoded image")
    return findings

