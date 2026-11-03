'use client';
import { useEffect, useRef, useState } from 'react';
import type { FaceLandmarker } from '@mediapipe/tasks-vision';
import { MotionProgress, yawDegrees } from './motionChallenge';
import type { MotionChallengeSpec } from '@/types/api';

export type CapturedFrame = { image: string; timestamp_ms: number };
export function useFaceGuidance(video: React.RefObject<HTMLVideoElement>, enabled: boolean) {
  const [guidance, setGuidance] = useState('Starting face guidance…');
  const [ready, setReady] = useState(false);
  const [recording, setRecording] = useState(false);
  const [blinks, setBlinks] = useState(0);
  const [frames, setFrames] = useState<CapturedFrame[]>([]);
  const [error, setError] = useState('');
  const [instruction, setInstruction] = useState('');
  const [completedSteps, setCompletedSteps] = useState(0);
  const [remainingSeconds, setRemainingSeconds] = useState(8);
  const attempt = useRef<{ start: number; frames: CapturedFrame[]; progress: MotionProgress; expires: number }>();
  const model = useRef<FaceLandmarker>();
  const cancel = () => { attempt.current = undefined; setRecording(false); setFrames([]); setBlinks(0); setError(''); setInstruction(''); setCompletedSteps(0); setRemainingSeconds(8); };

  useEffect(() => {
    if (!enabled) { cancel(); setReady(false); return; }
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    let detector: FaceLandmarker | undefined;
    let lastVideoTime = -1;
    const canvas = document.createElement('canvas');
    async function initialize() {
      try {
        const { FaceLandmarker, FilesetResolver } = await import('@mediapipe/tasks-vision');
        const files = await FilesetResolver.forVisionTasks('/mediapipe');
        detector = await FaceLandmarker.createFromOptions(files, {
          baseOptions: { modelAssetPath: '/mediapipe/face_landmarker.task', delegate: 'CPU' },
          runningMode: 'VIDEO', numFaces: 2, outputFacialTransformationMatrixes: true,
        });
        if (disposed) { detector.close(); return; }
        model.current = detector;
        tick();
      } catch { if (!disposed) { setError('Face guidance could not load. Retry the camera.'); setReady(false); } }
    }
    function tick() {
      if (disposed) return;
      try {
        const pending = attempt.current;
        if (pending && performance.now()-pending.start-(pending.frames.at(-1)?.timestamp_ms ?? 0) > 300) {
          throw new Error('Camera frames stopped arriving. Please retry.');
        }
        const element = video.current;
        if (element && element.readyState >= 2 && element.videoWidth && element.currentTime !== lastVideoTime && detector) {
          lastVideoTime = element.currentTime;
          const scale = Math.min(1, 480 / Math.max(element.videoWidth, element.videoHeight));
          canvas.width = Math.round(element.videoWidth * scale); canvas.height = Math.round(element.videoHeight * scale);
          canvas.getContext('2d')!.drawImage(element, 0, 0, canvas.width, canvas.height);
          const now = performance.now();
          const output = detector.detectForVideo(canvas, now);
          const faces = output.faceLandmarks;
          const face = faces.length === 1 ? faces[0] : undefined;
          const centred = !!face && face[1].x > .25 && face[1].x < .75 && face[1].y > .2 && face[1].y < .8;
          setReady(centred);
          setGuidance(faces.length > 1 ? 'Only one person should be visible.' : !face ? 'Position your face in the camera.' : !centred ? 'Move your face towards the centre.' : 'Face centred. Keep looking at the camera.');
          const current = attempt.current;
          if (current) {
            const elapsed = Math.round(now-current.start);
            const previous = current.frames.at(-1)?.timestamp_ms ?? 0;
            if (!centred || elapsed-previous > 250) throw new Error('Capture interrupted. Keep one face centred and retry.');
            if (Date.now() >= current.expires) throw new Error('Challenge expired. Start again.');
            if (elapsed > 8000 || current.frames.length >= 120) throw new Error('The actions were not completed in time. Please retry.');
            const distance = (a: number, b: number) => Math.hypot((face![a].x-face![b].x)*canvas.width, (face![a].y-face![b].y)*canvas.height);
            const ear = (ids: number[]) => (distance(ids[1],ids[5])+distance(ids[2],ids[4]))/(2*distance(ids[0],ids[3]));
            const openness = (ear([33,160,158,133,153,144])+ear([362,385,387,263,373,380]))/2;
            current.progress.update(openness, yawDegrees(output.facialTransformationMatrixes[0]), elapsed);
            if (current.progress.reason) throw new Error(current.progress.reason === 'wrong_direction'
              ? 'Turn in the requested direction. Start again.' : 'Follow the actions in the displayed order. Start again.');
            const image = canvas.toDataURL('image/jpeg', .7).split(',')[1];
            if (image.length > 100000) throw new Error('Camera image is too large. Please retry.');
            current.frames.push({ image, timestamp_ms: elapsed });
            if (current.frames.reduce((sum, frame) => sum + frame.image.length, 0) > 6000000) throw new Error('Capture is too large. Please retry.');
            setBlinks(current.progress.blinks);
            setInstruction(current.progress.instruction);
            setCompletedSteps(current.progress.step);
            setRemainingSeconds(Math.max(0, Math.ceil((8000 - elapsed) / 1000)));
            if (current.progress.complete && elapsed >= 1000 && current.frames.length >= 15) {
              setFrames(current.frames); attempt.current = undefined; setRecording(false);
            }
          }
        }
      } catch (cause) {
        attempt.current = undefined; setRecording(false); setFrames([]);
        setBlinks(0); setCompletedSteps(0); setInstruction('Start again when your face is centred.');
        setError(cause instanceof Error ? cause.message : 'Face tracking interrupted. Retry.');
      }
      timer = setTimeout(tick, 66);
    }
    void initialize();
    return () => { disposed = true; clearTimeout(timer); attempt.current = undefined; model.current = undefined; detector?.close(); };
  }, [enabled, video]);

  function start(spec: MotionChallengeSpec, expiresAt: string) {
    if (!ready || !model.current) throw new Error('Wait until your face is centred.');
    cancel();
    const expires = Date.parse(expiresAt);
    if (!Number.isFinite(expires) || expires <= Date.now()) throw new Error('Challenge expired. Start again.');
    const progress = new MotionProgress(spec);
    attempt.current = { start: performance.now(), frames: [], progress, expires };
    setInstruction(progress.instruction);
    setRecording(true);
  }
  return { guidance, ready, recording, blinks, frames, error, instruction, completedSteps, remainingSeconds, start, cancel };
}
