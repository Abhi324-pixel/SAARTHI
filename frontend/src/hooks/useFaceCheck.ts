import { RefObject, useEffect, useRef, useState } from 'react'
import { anglesFromMatrix, boxOf, distanceOf, fullyInFrame, isFacing, lightOf, lumaOf, type FaceBox, type Light } from '../lib/measure'

export interface FaceState {
  engine: 'loading' | 'ready' | 'error'
  faces: number
  inFrame: boolean
  distance: 'far' | 'ok' | 'close' | null
  yaw: number | null
  pitch: number | null
  roll: number | null
  facing: boolean
  light: Light | null
  box: FaceBox | null
}
export interface FaceStats { frames: number; oneFaceInFrame: number; facing: number }

const EMPTY: FaceState = { engine: 'loading', faces: 0, inFrame: false, distance: null, yaw: null, pitch: null, roll: null, facing: false, light: null, box: null }

let landmarkerPromise: Promise<any> | null = null
async function getLandmarker() {
  if (!landmarkerPromise) {
    landmarkerPromise = (async () => {
      const { FaceLandmarker, FilesetResolver } = await import('@mediapipe/tasks-vision')
      const files = await FilesetResolver.forVisionTasks('/mediapipe/wasm')
      const make = (delegate: 'GPU' | 'CPU') => FaceLandmarker.createFromOptions(files, {
        baseOptions: { modelAssetPath: '/mediapipe/face_landmarker.task', delegate },
        runningMode: 'VIDEO', numFaces: 2, outputFacialTransformationMatrixes: true,
      })
      try { return await make('GPU') } catch { return await make('CPU') }
    })().catch(e => { landmarkerPromise = null; throw e })
  }
  return landmarkerPromise
}

/** Runs the face model (bundled with the app, running fully in this browser) on the live video a few times a second.
 *  Reports what is actually measured: how many faces, whether the face is fully in the picture, how far, the head angles
 *  and the lighting. `stats` accumulates counters for the end-of-interview summary. */
export function useFaceCheck(video: RefObject<HTMLVideoElement | null>, active: boolean) {
  const [state, setState] = useState<FaceState>(EMPTY)
  const stats = useRef<FaceStats>({ frames: 0, oneFaceInFrame: 0, facing: 0 })
  const canvas = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    if (!active) return
    let stop = false
    let timer: number | undefined
    let lm: any = null
    getLandmarker().then(l => { lm = l; if (!stop) setState(s => ({ ...s, engine: 'ready' })) })
      .catch(() => { if (!stop) setState(s => ({ ...s, engine: 'error' })) })

    const tick = () => {
      const v = video.current
      if (!lm || !v || v.readyState < 2 || v.videoWidth === 0) return
      let res: any
      try { res = lm.detectForVideo(v, performance.now()) } catch { return }
      const faces = res.faceLandmarks?.length ?? 0
      let box: FaceBox | null = null
      let angles: { yaw: number; pitch: number; roll: number } | null = null
      if (faces >= 1) {
        box = boxOf(res.faceLandmarks[0])
        const m = res.facialTransformationMatrixes?.[0]?.data
        if (m && m.length === 16) angles = anglesFromMatrix(m)
      }
      // brightness from a small copy of the frame
      const c = (canvas.current ??= document.createElement('canvas'))
      c.width = 48; c.height = 36
      const ctx = c.getContext('2d', { willReadFrequently: true })
      let light: Light | null = null
      if (ctx) {
        ctx.drawImage(v, 0, 0, c.width, c.height)
        const img = ctx.getImageData(0, 0, c.width, c.height)
        light = lightOf(lumaOf(img), box ? lumaOf(img, box) : null)
      }
      const inFrame = !!box && fullyInFrame(box)
      const facing = !!angles && isFacing(angles)
      const s = stats.current
      s.frames++
      if (faces === 1 && inFrame) { s.oneFaceInFrame++; if (facing) s.facing++ }
      setState({ engine: 'ready', faces, inFrame, distance: box ? distanceOf(box) : null, yaw: angles?.yaw ?? null, pitch: angles?.pitch ?? null,
        roll: angles?.roll ?? null, facing: faces === 1 && inFrame && facing, light, box })
    }
    timer = window.setInterval(tick, 250)
    return () => { stop = true; if (timer) window.clearInterval(timer) }
  }, [active, video])

  return { state, stats }
}
