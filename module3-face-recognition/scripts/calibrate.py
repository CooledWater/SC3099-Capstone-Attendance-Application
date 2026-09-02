"""Calibrate the SimHash decision boundary against the supplied face corpus.

This script reads images only for the duration of the process. It prints
aggregate distances and quality measurements, never images, embeddings, or
templates.
"""

from __future__ import annotations

import argparse
import itertools
import sys
from dataclasses import dataclass
from pathlib import Path


MODULE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = MODULE_ROOT.parent
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from app.detection import detect_face  # noqa: E402
from app.embedding import extract_face_embedding  # noqa: E402
from app.imaging import decode_base64_image  # noqa: E402
from app.quality import assess_face_quality  # noqa: E402
from app.template import hamming_fraction, match_score, simhash_hex  # noqa: E402


OBAMA_IMAGES = (
    "obama.jpg",
    "obama2.jpg",
    "obama3.jpg",
    "obama_partial_face.jpg",
    "obama_partial_face2.jpg",
)
BIDEN_IMAGES = ("biden.jpg",)


@dataclass(frozen=True, slots=True)
class CalibratedImage:
    name: str
    template: str
    detection_confidence: float
    quality_score: float


def _encode(path: Path) -> CalibratedImage:
    encoded = None
    image = None
    embedding = None
    try:
        encoded = path.read_bytes()
        import base64

        image = decode_base64_image(base64.b64encode(encoded).decode("ascii"))
        detection = detect_face(image)
        if not detection.detected:
            raise RuntimeError(f"no face detected in {path.name}")
        embedding = extract_face_embedding(image, detection)
        quality = assess_face_quality(image, detection)
        return CalibratedImage(
            name=path.name,
            template=simhash_hex(embedding),
            detection_confidence=float(detection.confidence),
            quality_score=quality.score,
        )
    finally:
        embedding = None
        image = None
        encoded = None


def _pair_rows(
    pairs: list[tuple[CalibratedImage, CalibratedImage]], label: str
) -> list[tuple[str, str, str, float, float]]:
    rows: list[tuple[str, str, str, float, float]] = []
    for left, right in pairs:
        fraction = hamming_fraction(left.template, right.template)
        rows.append(
            (label, left.name, right.name, fraction, match_score(fraction))
        )
    return rows


def calibrate(image_directory: Path) -> float:
    required = (*OBAMA_IMAGES, *BIDEN_IMAGES)
    missing = [name for name in required if not (image_directory / name).is_file()]
    if missing:
        raise FileNotFoundError(
            "missing calibration images: " + ", ".join(sorted(missing))
        )

    samples = {name: _encode(image_directory / name) for name in required}
    obama = [samples[name] for name in OBAMA_IMAGES]
    biden = [samples[name] for name in BIDEN_IMAGES]

    intra_pairs = list(itertools.combinations(obama, 2))
    inter_pairs = [(left, right) for left in obama for right in biden]
    rows = _pair_rows(intra_pairs, "same") + _pair_rows(inter_pairs, "different")

    print("image                         confidence  quality")
    for sample in samples.values():
        print(
            f"{sample.name:29} {sample.detection_confidence:10.4f}  "
            f"{sample.quality_score:7.4f}"
        )
    print()
    print("kind       left                          right                         hamming  score")
    for label, left_name, right_name, fraction, score in rows:
        print(
            f"{label:10} {left_name:29} {right_name:29} "
            f"{fraction:7.4f}  {score:6.4f}"
        )

    maximum_intra = max(row[3] for row in rows if row[0] == "same")
    minimum_inter = min(row[3] for row in rows if row[0] == "different")
    print()
    print(f"maximum same-person Hamming fraction: {maximum_intra:.6f}")
    print(f"minimum different-person fraction:   {minimum_inter:.6f}")
    if maximum_intra >= minimum_inter:
        raise RuntimeError(
            "calibration failed: same-person and different-person distances overlap"
        )

    recommended = (maximum_intra + minimum_inter) / 2.0
    print(f"recommended FACE_MATCH_HAMMING_FRACTION={recommended:.6f}")
    return recommended


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--images",
        type=Path,
        default=REPOSITORY_ROOT / "sample_images",
        help="directory containing the supplied Obama and Biden JPEG files",
    )
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    try:
        calibrate(arguments.images.resolve())
    except Exception as exception:
        print(f"calibration error: {exception}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

