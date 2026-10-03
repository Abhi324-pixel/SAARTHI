// Real measurements taken in the browser from the learner's own camera and microphone. Nothing here is sent anywhere.
// The numbers are measured; the thresholds that turn them into advice ("a bit dark", "turn to face the camera") are plain
// rules of thumb, shown to the learner as guidance, never as a score.

export const LIMITS = {
  yawDeg: 20,        // head turned left/right
  pitchDeg: 20,      // face seen from above/below (camera too low or too high)
  rollDeg: 12,       // head tilted sideways (or camera rotated)
  faceWidthMin: 0.18, // face width as a fraction of the picture: smaller means too far away
  faceWidthMax: 0.55, // larger means too close
  edgeMargin: 0.02,  // the whole face must be inside the picture, with this margin
  darkLuma: 70,      // 0..255 average brightness
  brightLuma: 205,
  backlitGap: 50,    // background much brighter than the face
  speakingDb: -50,   // above this the microphone hears someone speaking (dBFS: 0 is the loudest possible)
  goodMinDb: -38,    // comfortable speaking range
  goodMaxDb: -8,
}

export function dbFromRms(rms: number): number {
  return 20 * Math.log10(Math.max(rms, 1e-6))
}

export type VoiceLevel = 'silent' | 'quiet' | 'good' | 'loud'
export function classifyVoice(db: number): VoiceLevel {
  if (db < LIMITS.speakingDb) return 'silent'
  if (db < LIMITS.goodMinDb) return 'quiet'
  if (db > LIMITS.goodMaxDb) return 'loud'
  return 'good'
}

/** Root-mean-square of a block of audio samples (-1..1). */
export function rmsOf(samples: Float32Array): number {
  let s = 0
  for (let i = 0; i < samples.length; i++) s += samples[i] * samples[i]
  return Math.sqrt(s / Math.max(samples.length, 1))
}

/** Head angles in degrees from a 4x4 face transform (16 numbers). Only the size of each angle is used, so row/column order
 *  and left/right conventions do not matter. Order of rotations: yaw (turn), then pitch (nod), then roll (tilt). */
export function anglesFromMatrix(m: ArrayLike<number>): { yaw: number; pitch: number; roll: number } {
  const r = (row: number, col: number) => m[col * 4 + row]            // column-major
  const sx = Math.hypot(r(0, 0), r(1, 0), r(2, 0)) || 1
  const sy = Math.hypot(r(0, 1), r(1, 1), r(2, 1)) || 1
  const sz = Math.hypot(r(0, 2), r(1, 2), r(2, 2)) || 1
  const R = [[r(0, 0) / sx, r(0, 1) / sy, r(0, 2) / sz], [r(1, 0) / sx, r(1, 1) / sy, r(1, 2) / sz], [r(2, 0) / sx, r(2, 1) / sy, r(2, 2) / sz]]
  const deg = 180 / Math.PI
  const pitch = Math.asin(Math.max(-1, Math.min(1, -R[1][2]))) * deg
  const yaw = Math.atan2(R[0][2], R[2][2]) * deg
  const roll = Math.atan2(R[1][0], R[1][1]) * deg
  return { yaw: Math.abs(yaw), pitch: Math.abs(pitch), roll: Math.abs(roll) }
}

export function isFacing(a: { yaw: number; pitch: number; roll: number }): boolean {
  return a.yaw <= LIMITS.yawDeg && a.pitch <= LIMITS.pitchDeg && a.roll <= LIMITS.rollDeg
}

export interface FaceBox { x: number; y: number; w: number; h: number }
export function boxOf(landmarks: { x: number; y: number }[]): FaceBox {
  let x0 = 1, y0 = 1, x1 = 0, y1 = 0
  for (const p of landmarks) { if (p.x < x0) x0 = p.x; if (p.y < y0) y0 = p.y; if (p.x > x1) x1 = p.x; if (p.y > y1) y1 = p.y }
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 }
}

export function fullyInFrame(b: FaceBox): boolean {
  const m = LIMITS.edgeMargin
  return b.x >= m && b.y >= m && b.x + b.w <= 1 - m && b.y + b.h <= 1 - m
}

export function distanceOf(b: FaceBox): 'far' | 'ok' | 'close' {
  return b.w < LIMITS.faceWidthMin ? 'far' : b.w > LIMITS.faceWidthMax ? 'close' : 'ok'
}

export type Light = 'dark' | 'ok' | 'bright' | 'backlit'
export function lightOf(frameLuma: number, faceLuma: number | null): Light {
  if (frameLuma < LIMITS.darkLuma) return 'dark'
  if (frameLuma > LIMITS.brightLuma) return 'bright'
  if (faceLuma !== null && frameLuma - faceLuma > LIMITS.backlitGap) return 'backlit'
  return 'ok'
}

/** Average brightness (0..255) of a region of a small canvas copy of the video frame. */
export function lumaOf(img: ImageData, box?: FaceBox): number {
  const { width: W, height: H, data } = img
  const x0 = box ? Math.max(0, Math.floor(box.x * W)) : 0
  const y0 = box ? Math.max(0, Math.floor(box.y * H)) : 0
  const x1 = box ? Math.min(W, Math.ceil((box.x + box.w) * W)) : W
  const y1 = box ? Math.min(H, Math.ceil((box.y + box.h) * H)) : H
  let sum = 0, n = 0
  for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) { const i = (y * W + x) * 4; sum += 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]; n++ }
  return n ? sum / n : 0
}
