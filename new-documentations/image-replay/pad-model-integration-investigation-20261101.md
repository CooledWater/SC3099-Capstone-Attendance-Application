# PAD models and Module 3 integration investigation

Investigated on 1 November 2026, Singapore time. Research and an isolated model compatibility probe only; no application code, policies, running services, attendance or files under `docs/` were changed.

Recommendation: evaluate the two-model MiniFASNet ensemble first, with anti-spoof-mn3 as a second lightweight candidate. MiniFASNet is a practical deployment baseline, not an established best-performing model for this application. Select the detector using separate genuine and attack captures from the supported cameras. Keep the existing motion requirement; a single-frame PAD model does not establish recording freshness or a trusted camera origin.

## What a PAD model does

Presentation attack detection (PAD) classifies whether the camera saw a genuine physical face or a presentation such as a printed/displayed face. Identity verification answers whether the face resembles the enrolled person. These are separate decisions. An enrolled person's photograph may correctly match their identity and still need to fail PAD.

A learned RGB PAD model uses labeled training examples to learn discriminative image features. It can respond to combinations of print/display texture, recapture artifacts and context that the current handcrafted FFT/color rules miss. It remains vulnerable to dataset and camera differences; it does not measure physical depth or guarantee detection of every attack. NIST's [2023 PAD evaluation](https://www.nist.gov/news-events/news/2023/09/whats-wrong-picture-nist-face-analysis-program-helps-find-answers) found substantial variation across algorithms and attack types. It is not evidence of MiniFASNet's performance on this project.

## How MiniFASNet works

MiniFASNet is the lightweight CNN family in Minivision's Silent-Face-Anti-Spoofing project. The [maintainer README](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/blob/master/README_EN.md) reports approximately 0.435 million parameters and 0.081 GFLOPs for V2, and explicitly cautions that results depend on the camera and scene. Its reported demo accuracy is not an accuracy guarantee for this application. The repository has an [Apache-2.0 license](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/blob/master/LICENSE); retain source/asset provenance and notices when packaging a selected artifact.

The [network source](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/blob/master/src/model_lib/MiniFASNet.py) uses inexpensive channel-wise convolutions, residual connections and a classification head. SE variants add channel attention. The term “depth-wise convolution” describes computation across image channels; it does not mean the network measures 3D face depth.

The released training pipeline combines classification cross-entropy with a Fourier-spectrum prediction loss, weighted 0.5 each in [train_main.py](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/blob/master/src/train_main.py). The auxiliary Fourier head encourages useful frequency features during training. [MultiFTNet.py](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/blob/master/src/model_lib/MultiFTNet.py) returns that auxiliary output during training and classification output during evaluation. Deployment does not require an extra FFT image supplied by the client. This is learned classification rather than another manually selected FFT cutoff.

The original [model directory](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/tree/master/resources/anti_spoof_models) supplies:

| Model | Input patch | Intended context scale |
| --- | --- | --- |
| `2.7_80x80_MiniFASNetV2.pth` | 80 × 80 | 2.7 × face bounding box |
| `4_0_0_80x80_MiniFASNetV1SE.pth` | 80 × 80 | 4.0 × face bounding box |

The [reference demo](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/blob/master/test.py) sums the two models' softmax class scores. Class index **1** means live; the other classes mean non-live. Do not assign specific print/screen meanings to those other indices without verifying training labels. The displayed demo score is confidence in the winning class, so a fake result can have confidence 0.99. Passing that value to SAIV as a high liveness score would reverse the intended meaning.

For a new calibrated policy, a useful scalar is the ensemble's live-class score:

```text
live_score = mean(softmax(logits_v2)[1], softmax(logits_v1se)[1])
pad_passed = live_score >= separately_calibrated_PAD_cutoff
```

This live-score threshold policy is a proposal, distinct from the reference demo's argmax decision. Softmax confidence is not a calibrated probability of physical presence. Do not reuse SAIV's 0.85 threshold automatically.

## Is it the best open-source model?

There is no support for that claim. Accuracy depends on the attack types, capture pipeline, genuine-user tolerance, evaluation split and deployment budget. A benchmark result on one dataset cannot rank models on this application's phone recaptures. This shortlist distinguishes readily deployable baselines from larger research comparators:

| Candidate | Evidence and practical fit | Assessment for SAIV |
| --- | --- | --- |
| MiniFASNet ensemble | Small CNNs, released weights, straightforward CPU execution | First integration baseline; local replay performance is unmeasured |
| [anti-spoof-mn3](https://github.com/openvinotoolkit/open_model_zoo/blob/master/models/public/anti-spoof-mn3/README.md) | MobileNetV3, 3.02M parameters, trained on CelebA-Spoof; original model listed under MIT | Worth comparing using the same local evaluation; its published ACER must not be compared directly with unrelated benchmark figures |
| [FLIP, ICCV 2023](https://github.com/koushiksrivats/FLIP) | CLIP-based cross-domain PAD; [benchmark-specific checkpoint links](https://github.com/koushiksrivats/FLIP/blob/main/docs/model_zoo.md) are published | Useful generalization research comparator; larger deployment/export exercise, checkpoint availability and redistribution terms need verification. No root license was found in the inspected repository listing |
| [FSFM / FS-VFM](https://huggingface.co/Wolowolo/fsfm-3c/blob/main/README.md) | More recent face-security transformer representations with released checkpoints; model card specifies research use and CC-BY-NC-4.0 | Research comparator with more integration work; an available model is not necessarily a permissively licensed deployment substitute. Select a PAD-finetuned checkpoint, not just an arbitrary pretrained/deepfake checkpoint |

The last two are public research releases, not equivalent to a small, permissively licensed drop-in classifier. No local head-to-head evaluation was performed, and this is not an exhaustive ranking of all published models.

## Integration traps verified in upstream source

1. **RGB versus BGR.** Module 3 decodes contiguous RGB uint8 arrays. The original MiniFASNet demo reads images with OpenCV and keeps BGR channel order through inference. Convert only the PAD input; preserve RGB for existing dlib/MediaPipe paths.
2. **Input scale.** The actual NumPy path in [functional.py](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/blob/master/src/data_io/functional.py) returns float values in **0–255**, without dividing by 255, despite a transform docstring describing 0–1. For these original weights, do not substitute standard torchvision normalization or ImageNet mean/std. An export that embeds preprocessing would require its own verified contract.
3. **Context crop.** Use the full decoded image and the PAD model's expanded box, rather than the current roughly 6%-margin `_face_crop()` used for texture. The original [crop helper](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/blob/master/src/generate_patches.py) limits scale to image bounds, shifts boxes near borders and resizes with OpenCV. A tight aligned identity crop or naive edge clipping changes the input distribution.
4. **Logits versus probabilities.** Confirm whether the selected ONNX graph includes softmax. Apply it exactly once, along the class axis. Validate finite outputs, dimensions and the live-class index.
5. **Demo behavior.** Do not copy its disk output, per-call model loading, or whole-frame 3:4 aspect-ratio guard into the API. The CNN consumes the model-specific patch. Preserve orientation and benchmark the application's actual frame aspect ratios and detector boxes.
6. **Converted artifacts.** The [community ONNX adapter](https://github.com/yakhyo/face-anti-spoofing/blob/main/onnx_inference.py) uses a different boundary crop implementation from the original helper. Its existence is useful deployment evidence, but a wrapper should not be adopted without checking preprocessing parity.

## Compatibility probe actually performed

The current face-service image is Linux aarch64 with OpenCV 4.11.0, and has no PyTorch, ONNX Runtime or ONNX package. I downloaded the [community ONNX releases](https://github.com/yakhyo/face-anti-spoofing#model-weights) and the original crop helper into `/tmp/saiv-pad-investigation-20261101/`, then ran both networks with `cv2.dnn.readNetFromONNX()` using the existing image.

The disposable container had no network, a read-only filesystem and read-only model mounts. It used only synthetic pixels, explicit bounding boxes, one OpenCV thread and CPU execution. For each model, three center/edge crop cases produced valid `1 × 3` finite outputs from `1 × 3 × 80 × 80` float32 input. After warmup, 60 `setInput + forward` measurements per model gave:

| Model | Size | Median | p95 | SHA-256 |
| --- | ---: | ---: | ---: | --- |
| V2 ONNX | 1,743,581 bytes | 1.554 ms | 1.646 ms | `b32929adc2d9c34b9486f8c4c7bc97c1b69bc0ea9befefc380e4faae4e463907` |
| V1SE ONNX | 1,742,335 bytes | 1.602 ms | 1.679 ms | `ebab7f90c7833fbccd46d3a555410e78d969db5438e169b6524be444862b3676` |

These timings exclude decoding, detection, crop generation, HTTP and concurrent load. They establish basic graph compatibility, not accuracy, production latency, original-PyTorch parity or correctness of the community conversion. No participant images were processed. The pair totals about 3.49 MB of ONNX assets.

This makes **existing OpenCV DNN the lowest-dependency prototype option**. ONNX Runtime remains an alternative if parity, performance or operator support calls for it. Verify original-PyTorch/exported-ONNX/OpenCV outputs on identical test tensors before release; pin the chosen graph and preprocessing together. Do not copy obsolete upstream training requirements into Module 3.

## Proposed Module 3 design

Add a model adapter with a small interface:

```python
evaluate_pad(image_rgb, face_bbox) -> PadAnalysis
# live_score, passed, model_version, inference_ms
# infrastructure/inference errors raise a dedicated unavailable exception
```

The adapter should use the existing face detector initially and check its box convention `(x, y, width, height)`. That detector differs from the original RetinaFace demo, so include box/crop differences in calibration. Do not add a second detector by default; establish whether it is necessary through evaluation.

Load/hash-check bundled assets and verify expected input/output shape. Maintain one model pair per worker thread or lock a shared pair: OpenCV `Net.setInput()` mutates inference state, so requests must not race on an unprotected global network. Reuse model objects; never cache frames, crops or landmarks. Bound CPU concurrency and benchmark on the deployment hardware.

Use server-side `PAD_MODE=off|shadow|enforce` configuration, with a pinned model version, hashes, crop metadata, live-class index, output type and a separately calibrated cutoff. These are proposed settings, not implemented environment variables. A request must not be able to turn enforcement off.

### Where it attaches

| File | Proposed responsibility |
| --- | --- |
| `app/pad.py` (new) | Model loading, preprocessing, inference and finite-output validation |
| `app/assets/pad/` (new) | Selected graphs, manifest, provenance and license notices; no runtime download |
| `app/config.py` | Mode, manifest/cutoff settings and startup validation |
| `app/liveness.py` | Shared PAD evaluation and approved score fusion, keeping original component diagnostics |
| `app/main.py` | Image endpoint result/error mapping and readiness initialization |
| `app/motion.py` | Ensure the sequence path receives PAD checks; extend frame sampling if approved |
| `app/motion_diagnostics.py` and Module 2 `app/checkin_diagnostics.py` | Explicit allowlists for bounded PAD scalar fields and version identifiers |
| `app/metrics.py` | Fixed-cardinality PAD outcome and latency metrics |
| `Dockerfile` / asset packaging | Include the selected graphs; existing OpenCV is sufficient for the tested prototype |

The shared insertion point is `assess_liveness()`: `/liveness/check` calls it with the full RGB image and detector box, and `analyze_sequence()` calls it for the first and last frames. Adding PAD only to the photo endpoint would leave the motion path unprotected. Checking only sequence endpoints still leaves intermediate-frame coverage incomplete; evaluate a bounded sampling policy across the sequence rather than claiming first/last checks protect every frame. Do not average away a detected attack with many high-scoring frames.

The existing native one-face and identity checks remain necessary. The current single-image `blink`/`head_turn` proxies do not become temporal proof simply because PAD is added. PAD also does not replace unpredictable motion or solve client-side camera injection.

### Proposed score and API behavior

Start in **shadow mode**, preserving current decisions and collecting only approved scalar comparisons. No historical replay pixels exist, so the previous scalar logs cannot be passed through a new model; fresh physical trials are required.

After validation and approval, use PAD as a veto instead of allowing favorable geometry, identity or risk to compensate for a spoof result. One conservative fusion is:

```text
legacy_score = current geometry-gated liveness score
final_score = legacy_score if pad_passed else 0.0
final_passed = legacy_passed and pad_passed
```

This preserves the existing approved geometry gates, the current 0.85 cutoff and top-level response shape. Retain `legacy_score` and `pad_live_score` separately in `details`; `final_score` is a decision score, not a probability. Define/test the configurable zero-cutoff edge explicitly so a PAD veto cannot become a pass. Any alternative that removes the existing gates or recalibrates the combined score is a separate policy change.

Proposed diagnostic fields: `pad_mode`, `pad_model_version`, `pad_live_score`, `pad_threshold`, `pad_passed`, `pad_inference_ms`, `pre_pad_liveness_score`. Missing/unperformed results must be marked unevaluated rather than reported as measured zero scores. The two existing diagnostic allowlists currently drop unknown fields, so response details alone will not make PAD observable in the monitor.

No new public endpoint or biometric storage table is needed for this integration. Existing Module 2 consumes `liveness_passed=false` and hard-rejects attendance independently of risk, so a valid PAD rejection can use that existing path. `/face/verify` and `/risk/assess` can retain their current responsibilities. Do not replace identity scores with PAD scores or pass the demo's winning-class confidence into risk assessment.

Asset corruption, model loading errors and invalid/non-finite outputs are **unavailable**, not measured spoof detections. Module 3 can map its dedicated unavailable exception through existing sanitized 503 handling. The backend's non-strict photo client turns non-200 responses into missing biometrics and can approve using other signals. Therefore, a Module 3-only deployment cannot guarantee PAD enforcement during outages. Existing strict mode blocks missing required evidence but changes other policies too. A narrowly scoped retry/manual-fallback policy requires a separate approved backend change. An uncertainty band and retry behavior also need an explicit contract rather than silently labeling uncertain captures live or spoofed.

## Validation and rollout

First verify export/preprocessing parity and compare MiniFASNet with anti-spoof-mn3 under the same physical capture protocol. The latter has its own preprocessing and live-class mapping; it cannot reuse MiniFASNet's manifest unchanged. Preserve the production photo/sequence resolution and JPEG settings during evaluation.

Use development captures to choose the PAD cutoff, then freeze the full pipeline and test separate people, cameras and presentation devices. Include genuine users, prints, high-resolution screens with weak artifacts, moved photos and the prepared two-blink video. Measure attack acceptance (APCER), genuine rejection (BPCER), failure-to-process, denominators, uncertainty and end-to-end latency/concurrency. Split by person/device/trial rather than randomly splitting neighboring video frames. Agree acceptable operating budgets before selecting a winner. No model has yet been evaluated on this local matrix.

Focused new tests belong under `new-tests/`: RGB/BGR and 0–255 preprocessing parity, original boundary crops, live-index/winning-class confidence, one-softmax behavior, manifest hashes, concurrent inference isolation, missing/corrupt assets, invalid outputs, shadow noninterference, PAD veto despite high legacy scores, photo/sequence coverage, scalar privacy and actual backend rejection/outage behavior. Keep native real-model checks distinct from mocked contract tests. Run the existing native suites in Module 3, backend suites in a separate process, and the relevant unchanged public HTTP tests on isolated services before implementation release.

Roll out shadow comparisons first, then an approved enforcement pilot. A rollout is successful only when the saved attendance behavior and genuine-user tolerance meet the agreed targets; passing the synthetic compatibility probe is insufficient. Keep manual attendance available. Enrollment/re-enrollment protection is a further scope decision: adding PAD there would affect the existing photo-based enrollment contract and should be designed explicitly.

## Specification boundaries and completed checks

The API currently specifies the liveness score/pass relationship and recommends the four-component calculation; the earlier approved exception adds 0.85 and geometry gates. A new PAD veto changes score semantics even if JSON fields remain stable. Obtain explicit approval under AGENTS.md rule 6 before enforcing such a change. Global failure-policy changes conflict with the integration guide's documented proceed-on-failure behavior. No conflicting implementation was made. `docs/` remains read-only.

Reviewed current Module 3 image, liveness, sequence, imaging, detection, configuration, diagnostics, metrics and container paths; Module 2 face-service results and check-in diagnostics; frontend capture paths; dashboard/session policy integration and the previous investigation. Verified original model/inference/training sources and alternative model release information. Existing application tests were not rerun because application code did not change; the preceding investigation's 82 passes are historical context for this turn, not new results.

Current checks: both downloaded ONNX graphs loaded and produced finite three-class outputs for all three synthetic crop cases; 60 timed runs per model succeeded. Runtime dependency inspection confirmed no PyTorch/ONNX Runtime installation. No live attendance endpoints, raw participant captures, running-service changes or production database writes were used.

Files changed: only this new report. Temporary downloaded model artifacts are outside the repository. Endpoints implemented: none. Proposed reuse: Module 3 `POST /liveness/check`, `POST /liveness/sequence`, `/face/verify`, `/risk/assess`; Module 2 existing motion proof and `POST /api/v1/checkins/` paths. Model choice, local cutoff, uncertainty/outage behavior, sequence sampling and final enforcement semantics remain decisions for the implementation stage.
