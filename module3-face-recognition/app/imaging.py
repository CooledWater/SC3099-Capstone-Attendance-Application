"""Secure, in-memory image decoding for the face-recognition service.

The functions in this module deliberately do not log input values and never
write decoded images to disk.  Images leave this module as contiguous RGB
``uint8`` arrays, which is the format expected by MediaPipe and dlib.
"""

from __future__ import annotations

import base64
import binascii
import re
import warnings
from io import BytesIO
from typing import Final

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

try:
    from .config import MAX_IMAGE_BYTES, MAX_IMAGE_DIM
except ImportError:  # pragma: no cover - supports direct, stand-alone imports
    MAX_IMAGE_BYTES = 8 * 1024 * 1024
    MAX_IMAGE_DIM = 1024


_DATA_URI_HEADER: Final[re.Pattern[str]] = re.compile(
    r"data:image/[a-z0-9.+-]+(?:;[^,;]+)*;base64",
    flags=re.IGNORECASE,
)
_ALLOWED_IMAGE_FORMATS: Final[frozenset[str]] = frozenset({"JPEG", "PNG"})
_ABSOLUTE_MAX_IMAGE_PIXELS: Final[int] = 32_000_000


class InvalidImageError(ValueError):
    """Raised when image input is malformed or cannot be decoded safely."""


class ImageTooLargeError(InvalidImageError):
    """Raised before decoding when an image exceeds the configured byte cap."""


class UnsafeImageError(InvalidImageError):
    """Raised when Pillow identifies a possible decompression-bomb image."""


def _split_data_uri(value: str) -> str:
    """Return the base64 payload from a plain value or an image data URI."""

    if not isinstance(value, str):
        raise InvalidImageError("Image must be a base64-encoded string")
    if not value:
        raise InvalidImageError("Image data is empty")

    if value[:5].lower() != "data:":
        return value

    header, separator, payload = value.partition(",")
    if not separator or _DATA_URI_HEADER.fullmatch(header) is None:
        raise InvalidImageError("Invalid image data URI")
    return payload


def _decode_base64(payload: str, max_bytes: int) -> bytes:
    """Strictly decode base64 after enforcing an encoded-size upper bound."""

    if not payload:
        raise InvalidImageError("Image data is empty")

    # Standard base64 requires groups of four.  Checking both the encoded
    # upper bound and padding before b64decode avoids allocating an oversized
    # decoded buffer.  The exact decoded size is checked again afterwards.
    max_encoded_chars = 4 * ((max_bytes + 2) // 3)
    if len(payload) > max_encoded_chars:
        raise ImageTooLargeError(f"Image exceeds the {max_bytes}-byte limit")
    if len(payload) % 4:
        raise InvalidImageError("Invalid base64 image data")

    try:
        encoded = payload.encode("ascii", errors="strict")
        decoded = base64.b64decode(encoded, validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
        raise InvalidImageError("Invalid base64 image data") from exc

    if not decoded:
        raise InvalidImageError("Image data is empty")
    if len(decoded) > max_bytes:
        raise ImageTooLargeError(f"Image exceeds the {max_bytes}-byte limit")
    return decoded


def _validated_limit(value: int | None, default: int, name: str) -> int:
    limit = default if value is None else value
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return limit


def _validate_image_header(image: Image.Image, max_dimension: int) -> None:
    """Reject unsupported, animated, or dangerously large image headers."""

    if image.format not in _ALLOWED_IMAGE_FORMATS:
        raise InvalidImageError("Only PNG and JPEG images are supported")
    if image.width <= 0 or image.height <= 0:
        raise InvalidImageError("Image dimensions are invalid")
    if bool(getattr(image, "is_animated", False)) or int(
        getattr(image, "n_frames", 1)
    ) != 1:
        raise InvalidImageError("Animated images are not supported")

    # Pillow's global bomb threshold is intentionally generous.  This tighter
    # request-local cap prevents a highly compressed image from allocating
    # hundreds of megabytes before it can be downscaled for detection.
    configured_cap = max(4_000_000, max_dimension * max_dimension * 16)
    pixel_cap = min(_ABSOLUTE_MAX_IMAGE_PIXELS, configured_cap)
    if image.width * image.height > pixel_cap:
        raise UnsafeImageError("Image dimensions exceed the safe pixel limit")


def decode_base64_image(
    base64_string: str,
    *,
    max_bytes: int | None = None,
    max_dimension: int | None = None,
) -> np.ndarray:
    """Decode an image into a contiguous RGB ``uint8`` NumPy array.

    Both raw base64 and ``data:image/...;base64,...`` values are accepted.
    Base64 syntax is validated strictly, compressed bytes are capped before
    decoding, EXIF orientation is applied, and large images are downscaled so
    their longest side is at most ``max_dimension``.

    Args:
        base64_string: Raw base64 or an image data URI.
        max_bytes: Optional compressed-byte cap.  Defaults to the service
            setting (8 MiB in development).
        max_dimension: Optional longest-side cap.  Defaults to the service
            setting (1024 pixels in development).

    Raises:
        InvalidImageError: For malformed base64, corrupt/unsupported images,
            or invalid image dimensions.
        ImageTooLargeError: When the compressed payload exceeds ``max_bytes``.
        UnsafeImageError: When Pillow's decompression-bomb protection fires.
    """

    byte_limit = _validated_limit(max_bytes, int(MAX_IMAGE_BYTES), "max_bytes")
    dimension_limit = _validated_limit(
        max_dimension, int(MAX_IMAGE_DIM), "max_dimension"
    )
    payload = _split_data_uri(base64_string)
    decoded = _decode_base64(payload, byte_limit)

    try:
        # Pillow normally emits a warning at its first header inspection.  It
        # is security-relevant here, so promote it to a typed hard failure.
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)

            # verify() validates the file structure without retaining decoded
            # pixels.  Re-opening afterwards is required by Pillow.
            with Image.open(BytesIO(decoded)) as candidate:
                _validate_image_header(candidate, dimension_limit)
                candidate.verify()

            with Image.open(BytesIO(decoded)) as source:
                _validate_image_header(source, dimension_limit)
                source.load()
                oriented = ImageOps.exif_transpose(source)
                try:
                    if oriented.width <= 0 or oriented.height <= 0:
                        raise InvalidImageError("Image dimensions are invalid")

                    rgb = oriented.convert("RGB")
                    try:
                        longest_side = max(rgb.size)
                        if longest_side > dimension_limit:
                            scale = dimension_limit / float(longest_side)
                            resized_size = (
                                max(1, int(round(rgb.width * scale))),
                                max(1, int(round(rgb.height * scale))),
                            )
                            resized = rgb.resize(resized_size, Image.Resampling.LANCZOS)
                            try:
                                array = np.asarray(resized, dtype=np.uint8).copy()
                            finally:
                                resized.close()
                        else:
                            array = np.asarray(rgb, dtype=np.uint8).copy()
                    finally:
                        rgb.close()
                finally:
                    if oriented is not source:
                        oriented.close()
    except InvalidImageError:
        raise
    except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise UnsafeImageError("Image dimensions exceed the safe limit") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise InvalidImageError("Decoded data is not a valid image") from exc
    finally:
        # Dropping the only module-local references promptly is intentional;
        # the caller owns only the normalized pixel array returned below.
        del decoded
        del payload

    if array.ndim != 3 or array.shape[2] != 3 or array.size == 0:
        raise InvalidImageError("Decoded image could not be converted to RGB")
    return np.ascontiguousarray(array, dtype=np.uint8)


__all__ = [
    "ImageTooLargeError",
    "InvalidImageError",
    "UnsafeImageError",
    "decode_base64_image",
]
