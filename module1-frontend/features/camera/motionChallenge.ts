import type { MotionChallengeSpec } from '@/types/api';

export const NEUTRAL_DEGREES = 8;
export const TURN_DEGREES = 20;
export const HOLD_MS = 200;

export function validChallenge(value: unknown): value is MotionChallengeSpec {
  if (!value || typeof value !== 'object') return false;
  const spec = value as MotionChallengeSpec;
  return spec.version === 2 && [1, 2].includes(spec.blink_target)
    && ['left', 'right'].includes(spec.turn_direction) && ['blink', 'head_turn'].includes(spec.first_action);
}

export function yawDegrees(matrix?: { rows: number; columns: number; data: number[] }): number {
  // MediaPipe's web pose packet is column-major; Python returns a 4x4 array.
  if (!matrix || matrix.rows !== 4 || matrix.columns !== 4 || matrix.data.length !== 16
    || !matrix.data.every(Number.isFinite) || Math.hypot(matrix.data[8], matrix.data[10]) < 1e-6) {
    throw new Error('Head tracking is unavailable. Please retry.');
  }
  return Math.atan2(matrix.data[8], matrix.data[10]) * 180 / Math.PI;
}

export class MotionProgress {
  baseline: number | null = null;
  baselineAt: number | null = null;
  baselineSamples: number[] = [];
  step = 0;
  holdAt: number | null = null;
  returning = false;
  neutralAt: number | null = null;
  turnPassed = false;
  reason = '';
  lastNeutral = false;
  lastOpen = false;
  open = false;
  closedAt: number | null = null;
  blinks = 0;
  readonly actions: ('blink' | 'head_turn')[];

  constructor(readonly spec: MotionChallengeSpec) {
    if (!validChallenge(spec)) throw new Error('Challenge version changed. Reload and start again.');
    this.actions = [spec.first_action, spec.first_action === 'blink' ? 'head_turn' : 'blink'];
  }

  get complete() {
    return this.baseline !== null && this.step === 2 && !this.reason && this.lastNeutral && this.lastOpen;
  }

  get instruction() {
    if (this.baseline === null) return 'Look straight at the camera with your eyes open.';
    if (this.step === 2) return 'Actions captured. Keep looking at the camera.';
    if (this.actions[this.step] === 'blink') return `Blink naturally ${this.spec.blink_target === 1 ? 'once' : 'twice'}.`;
    if (this.returning) return 'Return to the centre and hold briefly.';
    return `${this.spec.turn_direction === 'left' ? '←' : '→'} Turn your head to your ${this.spec.turn_direction} and hold briefly.`;
  }

  update(ear: number, yaw: number, timestamp: number) {
    // Keep temporal rules in parity with M3's random_motion.py.
    this.lastOpen = ear >= .23;
    if (this.reason) return;
    if (this.baseline === null) {
      if (Math.abs(yaw) <= NEUTRAL_DEGREES && this.lastOpen) {
        this.baselineAt ??= timestamp;
        this.baselineSamples.push(yaw);
        if (timestamp - this.baselineAt >= HOLD_MS) {
          this.baseline = this.baselineSamples.reduce((sum, value) => sum + value, 0) / this.baselineSamples.length;
          this.lastNeutral = true;
        }
      } else { this.baselineAt = null; this.baselineSamples = []; }
      return;
    }
    const delta = yaw - this.baseline;
    this.lastNeutral = Math.abs(delta) <= NEUTRAL_DEGREES;
    if (this.step === 2) {
      if (Math.abs(delta) >= TURN_DEGREES) this.reason = 'step_order';
      return;
    }
    if (this.actions[this.step] === 'blink') {
      if (Math.abs(delta) >= TURN_DEGREES) this.reason = 'step_order';
      else if (this.lastNeutral) {
        if (ear >= .23) {
          if (this.closedAt !== null && timestamp - this.closedAt >= 40 && timestamp - this.closedAt <= 700) this.blinks++;
          this.closedAt = null; this.open = true;
        } else if (ear < .19 && this.open) { this.closedAt = timestamp; this.open = false; }
        if (this.blinks >= this.spec.blink_target) this.step++;
      } else { this.open = false; this.closedAt = null; }
      return;
    }
    const directed = delta * (this.spec.turn_direction === 'left' ? 1 : -1);
    if (directed <= -TURN_DEGREES) this.reason = 'wrong_direction';
    else if (!this.returning) {
      if (directed >= TURN_DEGREES) {
        this.holdAt ??= timestamp;
        if (timestamp - this.holdAt >= HOLD_MS) this.returning = true;
      } else this.holdAt = null;
    } else if (this.lastNeutral && this.lastOpen) {
      this.neutralAt ??= timestamp;
      if (timestamp - this.neutralAt >= HOLD_MS) { this.turnPassed = true; this.step++; }
    } else this.neutralAt = null;
  }
}
