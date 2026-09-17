# Locally served face guidance assets

WASM files copied from `@mediapipe/tasks-vision` version 0.10.32 (Apache-2.0).
Model: Google's version-1 float16 Face Landmarker task bundle:
https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task

Keep WASM files in sync with the pinned npm dependency. Camera images are
processed locally for guidance; only the application's backend receives submitted
evidence. The model files are static assets, not captured biometric data.
