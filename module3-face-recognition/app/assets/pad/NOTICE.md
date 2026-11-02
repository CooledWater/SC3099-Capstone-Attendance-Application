# MiniFASNet asset provenance

Packaged for shadow evaluation on 1 November 2026. Both graphs use the Apache-2.0
licensed Minivision MiniFASNet architecture and pretrained weights. The ONNX
conversion is distributed by yakhyo/face-anti-spoofing, also under Apache-2.0.
The full license texts are adjacent to this file.

- Original source: https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/tree/b6d5f04ad78778917853b25c778acef6d5626d15
- Conversion source: https://github.com/yakhyo/face-anti-spoofing/tree/01a38903f4f2680bb59d32a994a6c7b5ae56f49b
- V2 graph: https://github.com/yakhyo/face-anti-spoofing/releases/download/weights/MiniFASNetV2.onnx
- V1SE graph: https://github.com/yakhyo/face-anti-spoofing/releases/download/weights/MiniFASNetV1SE.onnx
- Original weights: `resources/anti_spoof_models/2.7_80x80_MiniFASNetV2.pth`
  and `resources/anti_spoof_models/4_0_0_80x80_MiniFASNetV1SE.pth` in the original repository.

The graph bytes and preprocessing contract are pinned in `manifest.json` and
validated against constants in `app/pad.py`. GitHub release assets can be replaced;
the SHA-256 digests, rather than release URLs, identify the packaged bytes.
The community crop helper is not used. The application adapts Minivision's
`src/generate_patches.py` (2020, author zhuying, Minivision): context scales 2.7/4.0,
boundary shifting, inclusive end coordinates, OpenCV linear resize. This is a
modified integration with input validation, RGB-to-BGR conversion, and no disk
image output.

Input: BGR float32, 1×3×80×80, range 0–255 without mean/std normalization.
Output: three logits; exactly one softmax; live class is index 1. Other indices
are treated only as non-live. The ensemble score is the mean of live-class
scores. It is not a calibrated probability. The default 0.50 cutoff is solely an
exploratory comparison setting, separate from the legacy 0.85 liveness cutoff.

The runtime uses existing OpenCV DNN CPU support. No runtime download, PyTorch,
ONNX Runtime, or second face detector is required. The existing Dockerfile copies
this entire directory into the service image. See the integration report for
parity checks and known deployment limits.
