"""Isolated configuration/score checks; no camera, stored faces or live services."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

MODULE = Path(__file__).resolve().parents[1] / 'module3-face-recognition'
SCRIPT = '''
import json
from app.config import settings
from app.template import compare_templates
from app.motion_diagnostics import SequenceDiagnostics
reference = '0' * 64
diagnostic = SequenceDiagnostics()
diagnostic.observe('started')
print(json.dumps({
    'threshold': settings.face_match_threshold,
    'calibration': settings.face_match_calibration_threshold,
    'liveness': settings.liveness_threshold,
    'pad': settings.pad_threshold,
    'max_bits': settings.face_match_max_differing_bits,
    'diagnostic_max': diagnostic.snapshot()['max_accepted_hamming_distance'],
    'results': {str(bits): {'score': compare_templates(reference, f'{(1 << bits)-1:064x}').match_score,
                           'passed': compare_templates(reference, f'{(1 << bits)-1:064x}').match_passed}
                for bits in (0, 23, 30, 31, 52, 54, 256)},
}))
'''


def probe(demo=None, max_bits=None):
    env = {**os.environ, 'PYTHONPATH': str(MODULE), 'FACE_MATCH_THRESHOLD': '0.7',
           'FACE_MATCH_HAMMING_FRACTION': '0.08984375', 'LIVENESS_THRESHOLD': '0.85', 'PAD_THRESHOLD': '0.75'}
    env.pop('DEMO_FACE_MATCH_THRESHOLD', None)
    env.pop('FACE_MATCH_MAX_DIFFERING_BITS', None)
    if max_bits is not None:
        env['FACE_MATCH_MAX_DIFFERING_BITS'] = max_bits
    if demo is not None:
        env['DEMO_FACE_MATCH_THRESHOLD'] = demo
    return subprocess.run([sys.executable, '-c', SCRIPT], env=env, cwd=MODULE, capture_output=True, text=True)


def test_demo_lowers_actual_cutoff_without_rescaling_scores():
    normal = json.loads(probe().stdout)
    demo = json.loads(probe('0.5').stdout)
    assert normal['threshold'] == .7
    assert demo['threshold'] == .5
    assert normal['calibration'] == demo['calibration'] == .7
    for bits in normal['results']:
        assert normal['results'][bits]['score'] == demo['results'][bits]['score']
    assert normal['results']['30']['score'] == pytest.approx(.6533333333333333)
    assert normal['results']['30']['passed'] is False
    assert demo['results']['30']['passed'] is True
    assert demo['results']['52']['passed'] is True
    assert demo['results']['54']['passed'] is False
    assert normal['liveness'] == demo['liveness'] == .85
    assert normal['pad'] == demo['pad'] == .75
    # Removing the environment override restores the ordinary policy.
    assert json.loads(probe().stdout)['results']['30']['passed'] is False


@pytest.mark.parametrize('value', ['-0.1', '1.1', 'nan', 'not-a-number'])
def test_invalid_demo_threshold_is_rejected(value):
    assert probe(value).returncode != 0


def test_demo_hamming_cap_accepts_30_but_rejects_31_and_preserves_scores():
    uncapped = json.loads(probe('0.5').stdout)
    capped = json.loads(probe('0.5', '30').stdout)
    assert capped['max_bits'] == capped['diagnostic_max'] == 30
    assert capped['threshold'] == .5
    assert capped['results']['0']['passed'] is True
    assert capped['results']['30']['passed'] is True
    assert capped['results']['31']['passed'] is False
    assert capped['results']['256']['passed'] is False
    assert uncapped['results']['31']['passed'] is True
    for bits in capped['results']:
        assert capped['results'][bits]['score'] == uncapped['results'][bits]['score']
    assert json.loads(probe().stdout)['diagnostic_max'] == 23


@pytest.mark.parametrize('value', ['-1', '257', '30.5', 'bad'])
def test_invalid_hamming_cap_is_rejected(value):
    assert probe('0.5', value).returncode != 0
