"""Version 2 temporal challenge rules. All observations remain request-local."""
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NEUTRAL_DEGREES = 8.0
TURN_DEGREES = 20.0
HOLD_MS = 200


class ChallengeSpec(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    version: Literal[2]
    blink_target: int = Field(ge=1, le=2)
    turn_direction: Literal['left', 'right']
    first_action: Literal['blink', 'head_turn']


def yaw_degrees(matrix):
    """Positive yaw points to the subject's left in unmirrored camera pixels."""
    try:
        values = [[float(matrix[row][column]) for column in range(4)] for row in range(4)]
        if not all(math.isfinite(value) for row in values for value in row):
            raise ValueError('Non-finite pose')
        if math.hypot(values[0][2], values[2][2]) < 1e-6:
            raise ValueError('Degenerate pose')
        return math.degrees(math.atan2(values[0][2], values[2][2]))
    except (TypeError, IndexError, ValueError, OverflowError) as exc:
        raise ValueError('Invalid face rotation matrix') from exc


class MotionProgress:
    """Keep this temporal policy in parity with M1's motionChallenge.ts."""
    def __init__(self, spec, counter):
        self.spec = spec
        self.counter = counter
        self.actions = [spec.first_action, 'head_turn' if spec.first_action == 'blink' else 'blink']
        self.baseline = None
        self.baseline_at = None
        self.baseline_samples = []
        self.step = 0
        self.hold_at = None
        self.returning = False
        self.neutral_at = None
        self.turn_passed = False
        self.reason = None
        self.last_neutral = False
        self.last_open = False

    @property
    def complete(self):
        return self.baseline is not None and self.step == 2 and not self.reason and self.last_neutral and self.last_open

    def update(self, ear, yaw, timestamp):
        self.last_open = ear >= .23
        if self.reason:
            return
        if self.baseline is None:
            if abs(yaw) <= NEUTRAL_DEGREES and self.last_open:
                if self.baseline_at is None:
                    self.baseline_at = timestamp
                self.baseline_samples.append(yaw)
                if timestamp - self.baseline_at >= HOLD_MS:
                    self.baseline = sum(self.baseline_samples) / len(self.baseline_samples)
                    self.last_neutral = True
            else:
                self.baseline_at = None
                self.baseline_samples = []
            return
        delta = yaw - self.baseline
        self.last_neutral = abs(delta) <= NEUTRAL_DEGREES
        if self.step == 2:
            if abs(delta) >= TURN_DEGREES:
                self.reason = 'step_order'
            return
        if self.actions[self.step] == 'blink':
            if abs(delta) >= TURN_DEGREES:
                self.reason = 'step_order'
            elif self.last_neutral:
                self.counter.update(ear, timestamp)
                if self.counter.count >= self.spec.blink_target:
                    self.step += 1
            else:
                self.counter.open = False
                self.counter.closed_at = None
            return
        directed = delta * (1 if self.spec.turn_direction == 'left' else -1)
        if directed <= -TURN_DEGREES:
            self.reason = 'wrong_direction'
        elif not self.returning:
            if directed >= TURN_DEGREES:
                if self.hold_at is None:
                    self.hold_at = timestamp
                if timestamp - self.hold_at >= HOLD_MS:
                    self.returning = True
            else:
                self.hold_at = None
        elif self.last_neutral and self.last_open:
            if self.neutral_at is None:
                self.neutral_at = timestamp
            if timestamp - self.neutral_at >= HOLD_MS:
                self.turn_passed = True
                self.step += 1
        else:
            self.neutral_at = None

    def failure_reason(self):
        if self.reason:
            return self.reason
        if self.baseline is None:
            return 'baseline_missing'
        if self.step < 2:
            if self.actions[self.step] == 'blink':
                return 'insufficient_blinks'
            return 'neutral_not_restored' if self.returning else 'insufficient_turn'
        return 'neutral_not_restored' if not self.last_neutral else 'incomplete_blink'
