"""HTTP diagnostics preserve Hamming traces without changing public/persisted outcomes."""
import json

from test_video_replay_backend_diagnostics import world, start, verify
from app.database import SessionLocal
from app.motion import MotionChallenge


def test_hamming_trace_survives_backend_but_never_enters_public_response_or_database(world):
    client, uid, sid, state, records = world
    state['body']['diagnostics'].update({
        'simhash_bits':256,'face_match_hamming_fraction':.158203,'max_accepted_hamming_distance':40,
        'max_hamming_distance':39,'min_hamming_distance':16,
        'matcher_version':'dlib128-simhash256-v1','score_mapping_version':'piecewise-hamming-v1',
        'identity_comparisons_truncated':False,
        'identity_comparisons':[{'frame_index':0,'timestamp_ms':0,'hamming_distance':39,
            'hamming_fraction':39/256,'match_score':.7111,'match_passed':True,
            'hamming_evaluated':True,'face_detected':True,'template_hash':'PRIVATE_TEMPLATE',
            'embedding':['PRIVATE_TEMPLATE']}],
    })
    cid = start(world)
    response = verify(world, cid)
    assert response.status_code == 200
    assert set(response.json()) == {'passed','blink_count','liveness_score','face_match_score','verification_id'}
    sequence = next(row for row in records() if row['stage'] == 'motion_sequence')
    details = sequence['values']['diagnostics']
    assert sequence['session_id'] == sid and sequence['challenge_id'] == cid
    assert details['identity_comparisons'][0]['hamming_distance'] == 39
    assert details['max_accepted_hamming_distance'] == 40
    assert details['matcher_version'] == 'dlib128-simhash256-v1'
    assert 'PRIVATE_TEMPLATE' not in json.dumps(records())
    with SessionLocal() as db:
        persisted = json.loads(db.get(MotionChallenge,cid).result)
    assert set(persisted) == {'passed','blink_count','liveness_score','face_match_score'}


def test_hamming_trace_is_not_logged_when_diagnostics_are_disabled(world, monkeypatch):
    state, records = world[3], world[4]
    state['body']['diagnostics']['identity_comparisons'] = [{'hamming_distance':39}]
    monkeypatch.setenv('CHECKIN_DIAGNOSTICS_ENABLED','false')
    response = verify(world, start(world))
    assert response.status_code == 200 and 'diagnostics' not in response.json()
    assert records() == []
