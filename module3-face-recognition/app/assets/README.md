# Sequence landmark model

`face_landmarker.task` is Google's version-1 float16 Face Landmarker bundle,
copied from `module1-frontend/public/mediapipe/face_landmarker.task` so M1 and
M3 use the same eye landmark model with the existing blink thresholds.

Source: https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task

SHA-256: `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`

The model is bundled in M3's image; no runtime download or network access is
needed. Sequence processing checks the digest and fails closed if the asset
is missing, changed, or cannot load. Keep both model copies and the digest
in `app/motion.py` in sync when deliberately upgrading. The model is a
static asset and contains no participant images or enrollment data.
