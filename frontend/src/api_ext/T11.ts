export interface SpeechPauses {
  count_over_1s: number
  longest_s: number
}

export interface SpeechMetrics {
  words: number
  speaking_seconds: number
  wpm: number | null
  pauses: SpeechPauses
  markers: Record<string, number>
  markers_per_100_words: number
  tips: string[]
}

export interface InterviewSpeechReport {
  answers_with_audio: number
  median_wpm: number | null
  top_markers: { marker: string; count: number }[]
  tips: string[]
}

export const TIP_LABELS: Record<string, { en: string; hi: string; desc: string }> = {
  PACE_FAST: {
    en: 'Speaking quite fast (>170 WPM)',
    hi: 'थोड़ा तेज़ बोल रहे हैं',
    desc: 'Listeners usually find 110–160 words per minute easiest to follow.',
  },
  PACE_SLOW: {
    en: 'Speaking deliberately (<90 WPM)',
    hi: 'काफ़ी धीरे बोल रहे हैं',
    desc: 'A slightly brisk pace keeps your listener engaged.',
  },
  LONG_PAUSES: {
    en: 'Notable pauses between phrases',
    hi: 'वाक्यों के बीच ठहराव',
    desc: 'Pauses longer than 1 second give time to think, but too many can disrupt flow.',
  },
  MANY_MARKERS: {
    en: 'Frequent filler words / markers',
    hi: 'तकिया कलाम (fillers) का अधिक उपयोग',
    desc: 'Try pausing silently instead of using verbal filler words.',
  },
  GOOD: {
    en: 'Comfortable pace and natural delivery',
    hi: 'सहज गति और अच्छा प्रवाह',
    desc: 'Clear and easy to listen to.',
  },
}
