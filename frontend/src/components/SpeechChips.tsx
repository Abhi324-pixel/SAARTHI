import { useState } from 'react'
import { SpeechMetrics, TIP_LABELS } from '../api_ext/T11'
import { useApp } from '../store'

export function SpeechChips({ speech }: { speech?: SpeechMetrics | null }) {
  const { lang } = useApp()
  const [showExplainer, setShowExplainer] = useState(false)

  if (!speech) return null

  const markerList = Object.entries(speech.markers || {})
  const primaryTip = speech.tips?.[0]
  const tipInfo = primaryTip ? TIP_LABELS[primaryTip] : null

  return (
    <div className="mt-2 text-xs bg-paper border border-line rounded-xl p-2.5 space-y-1.5" role="region" aria-label="Speech coaching metrics">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="font-semibold text-navy">Speech delivery:</span>

          {speech.wpm !== null ? (
            <span className="chip" style={{ background: '#e3f2f1', color: '#0f5d5d' }} title={`${speech.words} words in ${speech.speaking_seconds}s of speaking`}>
              ⚡ {speech.wpm} words/min
            </span>
          ) : (
            <span className="chip text-muted" style={{ background: '#eceff3' }} title="Spoken utterance was too short to measure pace reliably">
              ⚡ Pace: too short to estimate
            </span>
          )}

          <span className="chip" style={{ background: speech.pauses.count_over_1s > 2 ? '#fdf3e9' : '#eceff3', color: speech.pauses.count_over_1s > 2 ? '#9a4f0a' : '#5b6675' }} title={`Longest pause was ${speech.pauses.longest_s}s`}>
            ⏸ {speech.pauses.count_over_1s} pause{speech.pauses.count_over_1s === 1 ? '' : 's'} &gt;1s
          </span>

          {markerList.length > 0 ? (
            markerList.map(([word, count]) => (
              <span key={word} className="chip" style={{ background: '#fdf3e9', color: '#9a4f0a' }}>
                “{word}” ×{count}
              </span>
            ))
          ) : (
            <span className="chip" style={{ background: '#e2f4ea', color: '#1f6f45' }}>
              ✓ No filler markers
            </span>
          )}
        </div>

        <button
          type="button"
          className="text-[11px] underline text-teal hover:text-navy cursor-pointer font-medium"
          onClick={() => setShowExplainer(!showExplainer)}
        >
          {showExplainer ? 'Close' : 'How is this measured?'}
        </button>
      </div>

      {tipInfo && (
        <div className="text-[11px] text-muted flex items-center gap-1">
          <span className="font-semibold text-navy">Tip:</span>
          <span>{lang === 'hindi' ? tipInfo.hi : tipInfo.en}</span>
          <span className="opacity-75">· {tipInfo.desc}</span>
        </div>
      )}

      {showExplainer && (
        <div className="text-[11px] text-muted border-t border-line pt-2 mt-1 space-y-1">
          <p>
            <b>Pace (WPM):</b> Total words spoken divided by active speaking time (leading and trailing silence are excluded).
          </p>
          <p>
            <b>Pauses:</b> Silences between consecutive words exceeding 1.0 second.
          </p>
          <p>
            <b>Markers:</b> Common conversational fillers (e.g. <i>basically, actually, you know, matlab</i>) matched directly in speech.
          </p>
          <p className="italic">
            This is supportive coaching only: it does not affect your score, will not change your mastery levels, and is never shared with mentors.
          </p>
        </div>
      )}
    </div>
  )
}
