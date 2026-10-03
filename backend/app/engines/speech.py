"""Speaking pace, pauses, and speech marker coaching (T11).

Pure engine functions for analyzing spoken responses.
Rules:
- Coaching only: never used for scoring, level changes, evidence, or mentor reports.
- Display-only: typed answers have no speech metrics.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"

# Threshold constants
FAST_WPM = 170
SLOW_WPM = 90
MIN_WORDS_FOR_WPM = 8
MIN_SECONDS_FOR_WPM = 5.0
PAUSE_THRESHOLD_SECONDS = 1.0
MAX_MARKERS_PER_100 = 6.0

_MARKERS_CACHE: Optional[dict[str, list[str]]] = None


def get_markers_config() -> dict[str, list[str]]:
    global _MARKERS_CACHE
    if _MARKERS_CACHE is None:
        p = CONTENT_DIR / "speech_markers.json"
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                _MARKERS_CACHE = json.load(f)
        else:
            _MARKERS_CACHE = {
                "english": ["um", "uh", "er", "you know", "i mean", "basically", "actually"],
                "hindi": ["matlab", "toh", "kya hai", "aisa hai ki", "yaani", "na"],
                "hinglish": ["matlab", "toh", "kya hai", "aisa hai ki", "yaani", "na", "um", "uh", "er", "you know", "i mean", "basically", "actually"],
            }
    return _MARKERS_CACHE


def _normalize_token(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def count_markers_in_tokens(tokens: list[str], marker_list: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for marker in marker_list:
        m_words = marker.lower().split()
        if not m_words:
            continue
        k = len(m_words)
        count = 0
        i = 0
        while i <= len(tokens) - k:
            if tokens[i : i + k] == m_words:
                count += 1
                i += k
            else:
                i += 1
        if count > 0:
            counts[marker] = count
    return counts


def analyze(
    words: Optional[list[dict[str, Any]]],
    language: str = "english",
) -> Optional[dict[str, Any]]:
    """Analyze a sequence of timestamped words.

    words item: {"text": str, "start": float, "end": float, "type": Optional[str]}
    Returns None if words is None or empty.
    """
    if not words:
        return None

    # Filter to items representing actual words
    valid_words = [
        w for w in words
        if w.get("text") and (w.get("type") in (None, "word") or "start" in w)
    ]
    if not valid_words:
        return None

    word_count = len(valid_words)
    first_start = float(valid_words[0].get("start", 0.0))
    last_end = float(valid_words[-1].get("end", 0.0))
    speaking_seconds = max(0.0, round(last_end - first_start, 2))

    # WPM
    wpm: Optional[int] = None
    if word_count >= MIN_WORDS_FOR_WPM and speaking_seconds >= MIN_SECONDS_FOR_WPM:
        wpm = int(round(word_count / (speaking_seconds / 60.0)))

    # Pauses inside utterance
    pauses_over_1s: list[float] = []
    for i in range(len(valid_words) - 1):
        curr_end = float(valid_words[i].get("end", 0.0))
        next_start = float(valid_words[i + 1].get("start", 0.0))
        gap = round(next_start - curr_end, 2)
        if gap > PAUSE_THRESHOLD_SECONDS:
            pauses_over_1s.append(gap)

    longest_pause = max(pauses_over_1s, default=0.0)
    pauses = {
        "count_over_1s": len(pauses_over_1s),
        "longest_s": longest_pause,
    }

    # Speech markers
    markers_cfg = get_markers_config()
    lang_key = (language or "english").lower()
    if lang_key in ("hi", "hindi"):
        marker_candidates = list(dict.fromkeys(markers_cfg.get("hindi", []) + markers_cfg.get("english", [])))
    elif lang_key in ("hinglish",):
        marker_candidates = markers_cfg.get("hinglish", []) or list(dict.fromkeys(markers_cfg.get("hindi", []) + markers_cfg.get("english", [])))
    else:
        marker_candidates = markers_cfg.get("english", [])

    tokens = [_normalize_token(w["text"]) for w in valid_words if _normalize_token(w["text"])]
    matched_markers = count_markers_in_tokens(tokens, marker_candidates)

    total_markers = sum(matched_markers.values())
    markers_per_100 = round((total_markers / word_count) * 100, 1) if word_count > 0 else 0.0

    # Tips
    tips: list[str] = []
    if wpm is not None:
        if wpm > FAST_WPM:
            tips.append("PACE_FAST")
        elif wpm < SLOW_WPM:
            tips.append("PACE_SLOW")

    if pauses["count_over_1s"] >= 2 or pauses["longest_s"] >= 3.0:
        tips.append("LONG_PAUSES")

    if markers_per_100 > MAX_MARKERS_PER_100:
        tips.append("MANY_MARKERS")

    if not tips:
        tips.append("GOOD")

    return {
        "words": word_count,
        "speaking_seconds": speaking_seconds,
        "wpm": wpm,
        "pauses": pauses,
        "markers": matched_markers,
        "markers_per_100_words": markers_per_100,
        "tips": tips,
    }
