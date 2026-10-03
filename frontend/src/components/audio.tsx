import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useApp } from '../store'
import { SpeechMetrics } from '../api_ext/T11'
import { Volume2, Mic, Square, Loader2 } from 'lucide-react'

/** Read-aloud via ElevenLabs Text-to-Speech (server proxy; the API key never reaches the browser). */
export function SpeakButton({ text, label = 'Listen' }: { text: string; label?: string }) {
  const { lang, toast } = useApp()
  const [state, setState] = useState<'idle' | 'loading' | 'playing'>('idle')
  const audio = useRef<HTMLAudioElement | null>(null)

  useEffect(() => () => { audio.current?.pause() }, [])

  async function play() {
    if (state === 'playing') {
      audio.current?.pause()
      setState('idle')
      return
    }
    setState('loading')
    try {
      const blob = await api.tts(text.replace(/\s+/g, ' ').slice(0, 900), lang)
      const url = URL.createObjectURL(blob)
      const a = new Audio(url)
      audio.current = a
      a.onended = () => {
        setState('idle')
        URL.revokeObjectURL(url)
      }
      await a.play()
      setState('playing')
    } catch (e: any) {
      setState('idle')
      toast(
        e?.message?.includes('VOICE') || e?.status === 503
          ? 'Voice is not set up yet (see docs/ELEVENLABS_SETUP.md).'
          : (e.message || 'Could not play audio'),
        'warn'
      )
    }
  }

  return (
    <button
      type="button"
      className="btn btn-secondary btn-sm flex items-center gap-1.5 text-xs py-1.5 px-3"
      onClick={play}
      aria-label={label}
      disabled={state === 'loading'}
    >
      {state === 'loading' ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin text-[var(--accent-orange)]" />
      ) : state === 'playing' ? (
        <Square className="w-3.5 h-3.5 text-[#FF5364] fill-current" />
      ) : (
        <Volume2 className="w-3.5 h-3.5 text-[#4D9DFF]" />
      )}
      <span>{state === 'loading' ? 'Synthesizing…' : state === 'playing' ? 'Stop Audio' : label}</span>
      <span className="chip" style={{ background: 'rgba(77,157,255,0.15)', color: '#4D9DFF', border: '1px solid rgba(77,157,255,0.3)', padding: '1px 5px', fontSize: '9px' }}>
        TTS
      </span>
    </button>
  )
}

/** Record speech in the browser, transcribe it with ElevenLabs Speech-to-Text, hand the text to the caller. */
export function MicButton({
  onText,
  onSpeech,
  disabled,
}: {
  onText: (t: string) => void
  onSpeech?: (s: SpeechMetrics | null) => void
  disabled?: boolean
}) {
  const { toast } = useApp()
  const [rec, setRec] = useState<'idle' | 'recording' | 'transcribing'>('idle')
  const [level, setLevel] = useState<number>(0)
  const mr = useRef<MediaRecorder | null>(null)
  const chunks = useRef<Blob[]>([])
  const audioCtx = useRef<AudioContext | null>(null)
  const animFrame = useRef<number | null>(null)

  function cleanupAudio() {
    if (animFrame.current) {
      cancelAnimationFrame(animFrame.current)
      animFrame.current = null
    }
    if (audioCtx.current) {
      audioCtx.current.close().catch(() => {})
      audioCtx.current = null
    }
    setLevel(0)
  }

  useEffect(() => () => cleanupAudio(), [])

  async function toggle() {
    if (rec === 'recording') {
      mr.current?.stop()
      cleanupAudio()
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunks.current = []
      recorder.ondataavailable = e => {
        if (e.data.size) chunks.current.push(e.data)
      }
      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        cleanupAudio()
        setRec('transcribing')
        try {
          const out = await api.stt(new Blob(chunks.current, { type: recorder.mimeType || 'audio/webm' }))
          if (out.text?.trim()) {
            onText(out.text.trim())
            onSpeech?.(out.speech ?? null)
          } else {
            toast("I couldn't hear anything — try speaking closer to the mic.", 'warn')
          }
        } catch (e: any) {
          toast(
            e.status === 503
              ? 'Speech-to-text is not set up yet (see docs/ELEVENLABS_SETUP.md).'
              : e.message,
            'warn'
          )
        } finally {
          setRec('idle')
        }
      }

      // Audio level analyser (fails soft if unsupported)
      try {
        const AudioCtxClass = window.AudioContext || (window as any).webkitAudioContext
        if (AudioCtxClass) {
          const ctx = new AudioCtxClass()
          audioCtx.current = ctx
          const source = ctx.createMediaStreamSource(stream)
          const analyser = ctx.createAnalyser()
          analyser.fftSize = 64
          source.connect(analyser)
          const dataArray = new Uint8Array(analyser.frequencyBinCount)

          const update = () => {
            analyser.getByteFrequencyData(dataArray)
            let sum = 0
            for (let i = 0; i < dataArray.length; i++) sum += dataArray[i]
            const avg = sum / dataArray.length
            setLevel(Math.min(100, Math.round((avg / 128) * 100)))
            animFrame.current = requestAnimationFrame(update)
          }
          update()
        }
      } catch {
        /* fail soft: recording continues without visual meter */
      }

      mr.current = recorder
      recorder.start()
      setRec('recording')
    } catch {
      toast('Microphone permission is needed for voice input. You can type instead.', 'warn')
    }
  }

  return (
    <div className="inline-flex items-center gap-2">
      <button
        type="button"
        onClick={toggle}
        disabled={disabled || rec === 'transcribing'}
        aria-pressed={rec === 'recording'}
        className={`btn btn-sm flex items-center gap-1.5 text-xs py-1.5 px-3 transition-all ${
          rec === 'recording'
            ? 'btn-orange pulse-ring shadow-[0_0_16px_rgba(255,138,36,0.4)]'
            : 'btn-secondary text-[var(--text-secondary)]'
        }`}
      >
        {rec === 'recording' ? (
          <Square className="w-3.5 h-3.5 fill-current text-white" />
        ) : rec === 'transcribing' ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin text-[var(--accent-orange)]" />
        ) : (
          <Mic className="w-3.5 h-3.5 text-[var(--accent-orange)]" />
        )}
        <span>{rec === 'recording' ? 'Stop' : rec === 'transcribing' ? 'Transcribing…' : 'Speak'}</span>
        <span
          className="chip"
          style={{
            background: 'rgba(255,138,36,0.15)',
            color: 'var(--accent-orange)',
            border: '1px solid rgba(255,138,36,0.3)',
            padding: '1px 5px',
            fontSize: '9px',
          }}
        >
          STT
        </span>
      </button>

      {rec === 'recording' && (
        <div
          className="w-12 h-2.5 bg-[rgba(20,32,44,0.6)] border border-[var(--border-subtle)] rounded-full overflow-hidden flex items-center p-0.5"
          title="Mic volume level"
        >
          <div
            className="h-full bg-[var(--accent-orange)] rounded-full transition-all duration-75 shadow-[0_0_8px_rgba(255,138,36,0.5)]"
            style={{ width: `${Math.max(5, level)}%` }}
          />
        </div>
      )}
    </div>
  )
}


