"""Optional export verification; torch/onnx are test tools, not service dependencies.

Supply --reference-dir containing original-MiniFASNet.py, original-V2.pth,
original-V1SE.pth, original_generate_patches.py from the pinned upstream commit
in app/assets/pad/NOTICE.md. All inference uses synthetic pixels, no face files.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import cv2
import numpy as np
import onnx
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'module3-face-recognition'))
from app.pad import MODEL_SPECS, preprocess, class_probabilities, context_box


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    reference = args.reference_dir
    original = load_module('original_minifasnet', reference / 'original-MiniFASNet.py')
    cropper = load_module('original_crop', reference / 'original_generate_patches.py').CropImage()
    torch.set_num_threads(1)
    cv2.setNumThreads(1)
    image = np.random.default_rng(3099).integers(0, 256, (160, 200, 3), dtype=np.uint8)
    boxes = [(80, 60, 40, 40), (0, 0, 40, 40), (160, 120, 40, 40), (0, 0, 200, 160)]
    report = {'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in reference.iterdir() if p.is_file() and p.suffix in ('.py', '.pth')},
        'numpy_seed': 3099, 'image_shape': [160, 200, 3], 'atol': 0.0001, 'rtol': 0.0001,
        'torch_version': torch.__version__, 'opencv_version': cv2.__version__, 'cases': []}
    for name, scale, digest in MODEL_SPECS:
        path = ROOT / 'module3-face-recognition/app/assets/pad' / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        graph = onnx.load(str(path))
        onnx.checker.check_model(graph)
        assert not any(node.op_type == 'Softmax' for node in graph.graph.node)
        assert graph.graph.output[0].type.tensor_type.shape.dim[-1].dim_value == 3
        variant = 'V2' if 'V2' in name else 'V1SE'
        net = getattr(original, 'MiniFASNet' + variant)(conv6_kernel=(5, 5))
        state = torch.load(reference / ('original-' + variant + '.pth'), map_location='cpu', weights_only=True)
        net.load_state_dict({key.removeprefix('module.'): value for key, value in state.items()})
        net.eval()
        dnn = cv2.dnn.readNetFromONNX(str(path))
        for box in boxes:
            assert context_box(image.shape, box, scale) == cropper._get_new_box(200, 160, box, scale)
            original_crop = cropper.crop(image[:, :, ::-1], box, scale, 80, 80)
            tensor = preprocess(image, box, scale)
            np.testing.assert_array_equal(tensor[0], original_crop.transpose(2, 0, 1))
            with torch.no_grad():
                expected = net(torch.from_numpy(tensor)).numpy()
            dnn.setInput(tensor)
            actual = dnn.forward()
            np.testing.assert_allclose(actual, expected, atol=report['atol'], rtol=report['rtol'])
            np.testing.assert_allclose(class_probabilities(actual), torch.softmax(torch.from_numpy(expected), 1).numpy()[0],
                                       atol=report['atol'], rtol=report['rtol'])
            report['cases'].append({'model': name, 'scale': scale, 'bbox': list(box),
                'reference_logits': expected.tolist(), 'opencv_logits': actual.tolist(),
                'max_absolute_error': float(np.max(np.abs(actual - expected)))})
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f"Verified {len(report['cases'])} original-PyTorch / ONNX-OpenCV comparisons and crop parity; "
          f"max logit error {max(row['max_absolute_error'] for row in report['cases']):.8f}")


if __name__ == '__main__':
    main()
