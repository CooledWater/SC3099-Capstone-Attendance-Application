"""Authenticated, expiring motion challenges. Never persists captured frames."""
import json
import secrets
import uuid
from typing import Literal
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict, model_validator
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Integer, CheckConstraint
from sqlalchemy.orm import Session
from app.database import Base
from app.session_lifecycle import get_session_db
from app import checkin_diagnostics
from app.auth import require_roles
from app.models import User, Session as AttendanceSession, Enrollment, CheckIn
from app.face_service import face_service, LivenessResult, FaceMatchResult, RiskResult
import httpx


class MotionPolicy(Base):
    __tablename__ = 'session_motion_policies'
    session_id = Column(String(36), ForeignKey('sessions.id', ondelete='CASCADE'), primary_key=True)
    required = Column(Boolean, nullable=False, default=False)


class MotionChallenge(Base):
    __tablename__ = 'motion_challenges'
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False)
    reference_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    state = Column(String(16), nullable=False, default='issued')
    result = Column(Text, nullable=True)


class StartChallenge(BaseModel):
    model_config = ConfigDict(extra='forbid')
    session_id: str


class ChallengeSpec(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    version: Literal[2]
    blink_target: int = Field(ge=1, le=2)
    turn_direction: Literal['left', 'right']
    first_action: Literal['blink', 'head_turn']


class MotionChallengeSpec(Base):
    """Immutable scalar requirements, kept separate from verification outcomes."""
    __tablename__ = 'motion_challenge_specs'
    challenge_id = Column(String(36), ForeignKey('motion_challenges.id', ondelete='CASCADE'), primary_key=True)
    version = Column(Integer, nullable=False)
    blink_target = Column(Integer, nullable=False)
    turn_direction = Column(String(5), nullable=False)
    first_action = Column(String(9), nullable=False)
    __table_args__ = (
        CheckConstraint('version = 2'),
        CheckConstraint('blink_target IN (1, 2)'),
        CheckConstraint("turn_direction IN ('left', 'right')"),
        CheckConstraint("first_action IN ('blink', 'head_turn')"),
    )

    def descriptor(self):
        return ChallengeSpec(**{key: getattr(self, key) for key in
                                ('version', 'blink_target', 'turn_direction', 'first_action')}).model_dump()


def delete_challenges(db, query):
    """Explicit child cleanup supports SQLite tests without FK enforcement too."""
    db.query(MotionChallengeSpec).filter(MotionChallengeSpec.challenge_id.in_(
        query.with_entities(MotionChallenge.id))).delete(synchronize_session=False)
    return query.delete(synchronize_session=False)


def issued_spec(db, challenge_id):
    row = db.get(MotionChallengeSpec, challenge_id)
    if row is None:
        raise HTTPException(409, 'Challenge version changed; start a new challenge')
    try:
        return row.descriptor()
    except ValueError:
        raise HTTPException(409, 'Invalid challenge; start a new challenge')


class Frame(BaseModel):
    model_config = ConfigDict(extra='forbid')
    image: str = Field(min_length=1, max_length=100_000)
    timestamp_ms: int = Field(ge=0, le=8000, strict=True)


class Sequence(BaseModel):
    model_config = ConfigDict(extra='forbid')
    frames: list[Frame] = Field(min_length=15, max_length=120)

    @model_validator(mode='after')
    def bounded_sequence(self):
        times = [f.timestamp_ms for f in self.frames]
        if sum(len(f.image) for f in self.frames) > 6_000_000:
            raise ValueError('Sequence is too large')
        if times[0] > 250 or times[-1] - times[0] < 1000:
            raise ValueError('Capture a complete sequence')
        if any(not 0 < b-a <= 250 for a, b in zip(times, times[1:])):
            raise ValueError('Frames must be ordered with gaps no larger than 250ms')
        return self


router = APIRouter(prefix='/api/v1/motion', tags=['motion'])


def required(db, session_id):
    policy = db.get(MotionPolicy, session_id)
    return bool(policy and policy.required)


def eligible(db, user, session_id):
    session = db.get(AttendanceSession, session_id)
    now = datetime.utcnow()
    if not session or session.status != 'active' or not session.checkin_opens_at <= now <= session.checkin_closes_at:
        raise HTTPException(400, 'Session is not open for check-in')
    if not db.query(Enrollment).filter_by(student_id=user.id, course_id=session.course_id, is_active=True).first():
        raise HTTPException(403, 'You are not enrolled in this course')
    if db.query(CheckIn).filter_by(student_id=user.id, session_id=session_id).first():
        raise HTTPException(409, 'Already checked in')
    if not user.camera_consent or not user.face_enrolled or not user.face_embedding_hash:
        raise HTTPException(400, 'Camera consent and face enrollment are required')
    return session


@router.post('/challenges', status_code=201)
def start(payload: StartChallenge, user: User = Depends(require_roles('student')), db: Session = Depends(get_session_db)):
    session = eligible(db, user, payload.session_id)
    with checkin_diagnostics.capture(session.id, start_stage=None, failure_stage='motion_request_failed'):
        # Serialize issuance per user so concurrent retries cannot leave two active attempts.
        db.query(User).filter_by(id=user.id).with_for_update().first()
        delete_challenges(db, db.query(MotionChallenge).filter(MotionChallenge.expires_at < datetime.utcnow()))
        delete_challenges(db, db.query(MotionChallenge).filter_by(user_id=user.id, session_id=session.id))
        item = MotionChallenge(user_id=user.id, session_id=session.id, reference_hash=user.face_embedding_hash,
                               expires_at=min(datetime.utcnow()+timedelta(minutes=3), session.checkin_closes_at))
        db.add(item); db.flush()
        spec = MotionChallengeSpec(challenge_id=item.id, version=2,
                                   blink_target=secrets.choice((1, 2)),
                                   turn_direction=secrets.choice(('left', 'right')),
                                   first_action=secrets.choice(('blink', 'head_turn')))
        db.add(spec)
        # Snapshot before commit: a concurrent retry may delete this row as
        # soon as the per-user lock is released. Never lazy-load it afterward.
        body = {'challenge_id': item.id, 'action': 'random_motion', 'challenge': spec.descriptor(),
                'expires_at': item.expires_at.isoformat()+'Z', 'max_duration_ms': 8000, 'max_frames': 120}
        db.commit()
        checkin_diagnostics.bind_challenge(body['challenge_id'])
        checkin_diagnostics.event('motion_challenge_issued', max_duration_ms=8000, max_frames=120)
        return body


@router.post('/challenges/{challenge_id}/verify')
def verify(challenge_id: str, payload: Sequence, user: User = Depends(require_roles('student')), db: Session = Depends(get_session_db)):
    item = db.get(MotionChallenge, challenge_id)
    if not item or item.user_id != user.id:
        raise HTTPException(404, 'Challenge not found')
    with checkin_diagnostics.capture(item.session_id, challenge_id=item.id,
                                     start_stage='motion_verification_started', failure_stage='motion_request_failed'):
        eligible(db, user, item.session_id)
        if item.reference_hash != user.face_embedding_hash:
            raise HTTPException(409, 'Enrollment changed; start a new challenge')
        spec = issued_spec(db, item.id)
        claimed = db.query(MotionChallenge).filter_by(id=item.id, state='issued').filter(
            MotionChallenge.expires_at > datetime.utcnow()).update({'state': 'processing'}, synchronize_session=False)
        db.commit()
        if not claimed:
            raise HTTPException(409, 'Challenge expired or already submitted; start again')
        try:
            response = face_service._post('/liveness/sequence', {
                'frames': [f.model_dump() for f in payload.frames], 'reference_template_hash': user.face_embedding_hash,
                'challenge': spec,
            }, 45.0)
            if response.status_code != 200:
                raise ValueError('Unusable service response')
            result = response.json()
            # Validate every persisted field; never trust an arbitrary service response.
            if not isinstance(result, dict) or type(result.get('passed')) is not bool:
                raise ValueError('Invalid result')
            for key in ('liveness_score', 'face_match_score'):
                value = result.get(key)
                if type(value) not in (int, float) or not 0 <= value <= 1:
                    raise ValueError('Invalid score')
            safe = {key: result[key] for key in ('passed', 'liveness_score', 'face_match_score')}
            count = result.get('blink_count')
            if type(count) is not int or not 0 <= count <= 60:
                raise ValueError('Invalid blink count')
            safe['blink_count'] = count
            if type(result.get('challenge_version')) is not int or result['challenge_version'] != 2:
                raise ValueError('Missing versioned challenge evidence')
            if type(result.get('turn_passed')) is not bool:
                raise ValueError('Invalid turn evidence')
            steps = result.get('completed_steps')
            if type(steps) is not int or not 0 <= steps <= 2:
                raise ValueError('Invalid action evidence')
            safe.update(challenge_version=2, turn_passed=result['turn_passed'], completed_steps=steps)
            if safe['passed'] and (count < spec['blink_target'] or not safe['turn_passed'] or steps != 2):
                raise ValueError('Missing required motion evidence')
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            db.query(MotionChallenge).filter_by(id=challenge_id).update({'state': 'failed'})
            db.commit()
            raise HTTPException(503, 'Motion verification unavailable; start a new challenge')
        updated = db.query(MotionChallenge).filter_by(id=challenge_id, state='processing').filter(
            MotionChallenge.expires_at > datetime.utcnow()).update({
                'state': 'verified' if safe['passed'] else 'failed', 'result': json.dumps(safe)}, synchronize_session=False)
        db.commit()
        if not updated:
            raise HTTPException(409, 'Challenge expired or was replaced; start again')
        checkin_diagnostics.event('motion_verified', **safe)
        return {**safe, 'verification_id': challenge_id if safe['passed'] else None}


def consume(db, user, session_id, verification_id):
    if not user.camera_consent:
        raise HTTPException(400, 'Camera consent is required')
    item = db.get(MotionChallenge, verification_id)
    if not item or item.user_id != user.id or item.session_id != session_id or item.reference_hash != user.face_embedding_hash:
        raise HTTPException(400, 'Verification does not match this student and session')
    issued_spec(db, item.id)  # Old two-blink proofs cannot survive the rollout.
    changed = db.query(MotionChallenge).filter_by(id=item.id, state='verified').filter(
        MotionChallenge.expires_at > datetime.utcnow()).update({'state': 'consumed'}, synchronize_session=False)
    if not changed:
        raise HTTPException(409, 'Verification expired or already used; repeat the challenge')
    # This update commits atomically with the attendance insert in main.py.
    result = json.loads(item.result)
    score = result['liveness_score']; match = result['face_match_score']
    return {'liveness': LivenessResult(True, score, 'random_motion', None),
            'face_match': FaceMatchResult(True, match, None),
            'module3_risk': RiskResult(max(1-score, 1-match), '', {}, []),
            'face_embedding_hash': None}


class MotionBodyLimit:
    """Bound actual body bytes, including chunked uploads, before JSON parsing."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get('type') != 'http' or not scope.get('path', '').startswith('/api/v1/motion/'):
            return await self.app(scope, receive, send)
        from starlette.responses import JSONResponse
        chunks = []; size = 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            chunk = message.get('body', b''); size += len(chunk)
            if size > 6_200_000:
                return await JSONResponse({'detail': 'Sequence upload is too large'}, status_code=413)(scope, receive, send)
            chunks.append(chunk)
            if not message.get('more_body', False): break
        delivered = False
        async def replay():
            nonlocal delivered
            if delivered: return await receive()
            delivered = True
            return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
        return await self.app(scope, replay, send)
