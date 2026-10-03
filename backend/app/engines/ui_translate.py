"""I18N: translate interface text into Hindi (Devanagari) or Hinglish (Hindi in Roman letters), with a permanent shared cache.

How it stays trustworthy:
- Every translated string is checked by code before it is used or stored: same numbers, the right script, a sensible length. A string
  that fails any check is simply left in English, never replaced by a guess.
- Technical words, code, product names and person names are kept as they are (the instruction to the model says so, and the numbers check
  catches most damage to anything with digits).
- Text that looks like personal data (e-mail, link, phone number) is not sent anywhere and not stored.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..llm import gateway
from ..models_ext.I18N import UiTranslation

log = logging.getLogger("saarthi.i18n")

LANGS = {"hindi": "Hindi in Devanagari script", "hinglish": "Hinglish: Hindi written in Roman (Latin) letters, as people text in India"}
MAX_BATCH = 40
SEND_BATCH = 12        # smaller batches make the model translate each text instead of copying a long list
MAX_LEN = 400
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
PERSONAL = re.compile(r"(https?://|www\.|@\w+\.\w+|\b\d{10}\b|\+\d{1,3}[\s-]?\d{8,})", re.I)

_EXAMPLES = {
    "hindi": [("Python basics", "Python की बुनियादी बातें"), ("79% · developing", "79% · विकसित हो रहा है"), ("not assessed", "अभी मूल्यांकित नहीं"),
              ("Start the quick check", "त्वरित जाँच शुरू करें"), ("INNER JOIN", "INNER JOIN"), ("Is concept mein abhi 12% hai", "इस कॉन्सेप्ट में अभी 12% है")],
    "hinglish": [("Python basics", "Python ke basics"), ("79% · developing", "79% · seekh rahe hain"), ("not assessed", "abhi assess nahi hua"),
                 ("Start the quick check", "Quick check shuru karein"), ("INNER JOIN", "INNER JOIN"), ("Save", "Save karein")],
}

_SYSTEM = (
    "You translate short user-interface texts of SAARTHI, a learning app, from English into {target}.\n"
    "Rules: (1) Translate every ordinary word, including headings, labels, level words (developing, proficient, not assessed) and concept names "
    "such as 'Python basics'. Keep ONLY these unchanged: programming keywords and code (SELECT, INNER JOIN, GROUP BY, HTTP, API), table and column "
    "names, file names, product and place names (SAARTHI, ElevenLabs, Vakh, Tavily, Gemini, Supabase, Chhatrachhaya, Margdarshak, YouTube), "
    "and person names. (2) Keep every number exactly, using ASCII digits 0-9, and keep symbols and emoji. (3) Keep any text inside curly "
    "quotes “…” unchanged. (4) Keep the meaning and a similar length: buttons and labels must stay short. (5) A text that is already in the "
    "requested form is returned unchanged; a text in the other Hindi form (Hinglish when Hindi is requested, or the reverse) is converted. "
    "(6) Translate each text on its own. Return exactly one translation per input text, in the same order, nothing else.\n"
    "Examples:\n{examples}"
)

_SCHEMA = {"type": "object", "properties": {"translations": {"type": "array", "items": {"type": "string"}}}, "required": ["translations"]}


def _key(lang: str, source: str) -> str:
    return hashlib.sha256(f"{lang}\n{source}".encode("utf-8")).hexdigest()


def _has_ordinary_word(t: str) -> bool:
    """True if the text has at least one word that is not ALL-CAPS code. 'INNER JOIN' or 'SQL' have none (code); 'Save' or 'Python basics' do."""
    return any(len(w) >= 3 and not w.isupper() for w in re.findall(r"[A-Za-z][A-Za-z']*", t))


def eligible(text: str) -> bool:
    """Only plain interface sentences are translated. Personal-looking text, huge text, symbol-only text, and names or code are not."""
    t = text.strip()
    return bool(t) and len(t) <= MAX_LEN and bool(re.search(r"[A-Za-z]{2}", t)) and not PERSONAL.search(t) and _has_ordinary_word(t)


def _valid(lang: str, src: str, out: str) -> bool:
    out = out.strip()
    if not out or len(out) > max(len(src) * 3, 60):
        return False
    if sorted(re.findall(r"\d+", src)) != sorted(re.findall(r"\d+", out)):
        return False
    if lang == "hinglish" and DEVANAGARI.search(out):
        return False
    if lang == "hindi" and not DEVANAGARI.search(out):
        return False                      # "Hindi" must be in Devanagari
    if out == src.strip() and _has_ordinary_word(src):
        # unchanged is fine only for a short Hinglish label ("Skill graph"): Hinglish keeps many English words. Never for Hindi or a sentence.
        return lang == "hinglish" and len(src.split()) <= 4
    return True


def translate(db: Session, lang: str, texts: list[str]) -> list[Optional[str]]:
    """One entry per input: the translation, or None when it should stay as it is (not eligible, invalid, or the model is unavailable)."""
    if lang not in LANGS:
        raise ValueError("unsupported language")
    out: list[Optional[str]] = [None] * len(texts)
    todo: dict[str, list[int]] = {}
    cached = {r.key: r.translated for r in db.scalars(select(UiTranslation).where(UiTranslation.lang == lang, UiTranslation.key.in_([_key(lang, t.strip()) for t in texts if eligible(t)])))}
    for i, raw in enumerate(texts):
        if not eligible(raw):
            continue
        s = raw.strip()
        k = _key(lang, s)
        if k in cached:
            out[i] = cached[k]
        else:
            todo.setdefault(s, []).append(i)
    pending = list(todo)
    for start in range(0, len(pending), SEND_BATCH):
        for src, tr in _ask(lang, pending[start:start + SEND_BATCH]).items():
            try:
                with db.begin_nested():
                    db.add(UiTranslation(key=_key(lang, src), lang=lang, source=src, translated=tr))
                    db.flush()
            except IntegrityError:
                pass
            for i in todo[src]:
                out[i] = tr
    return out


def _ask(lang: str, batch: list[str], retry: bool = True) -> dict[str, str]:
    """Ask the model for one batch. If its answer has the wrong number of items, ask again for each half, so one bad text cannot spoil the rest."""
    if not batch:
        return {}
    examples = "\n".join(f"{a}  ->  {b}" for a, b in _EXAMPLES[lang])
    try:
        raw = gateway.generate_json("ui_translate", _SYSTEM.format(target=LANGS[lang], examples=examples), "TEXTS (JSON array):\n" + _json(batch), _SCHEMA,
                                    fake=lambda b=batch: {"translations": [f"[{lang}] {x}" for x in b]}, max_tokens=4000, temperature=0.1)
        result = raw.get("translations")
    except Exception as e:
        log.warning("translation batch failed: %s", type(e).__name__)
        return {}
    if not isinstance(result, list) or len(result) != len(batch):
        log.warning("translation batch returned %s items for %s", len(result) if isinstance(result, list) else "no", len(batch))
        if len(batch) == 1:
            return {}
        mid = len(batch) // 2
        return {**_ask(lang, batch[:mid], retry), **_ask(lang, batch[mid:], retry)}
    good = {}
    for src, tr in zip(batch, result):
        tr = str(tr).strip()
        if _valid(lang, src, tr):
            good[src] = tr
    failed = [b for b in batch if b not in good]
    if failed and retry:                                   # the model slipped inside a long list: ask again for just those, in small groups
        for i in range(0, len(failed), 4):
            good.update(_ask(lang, failed[i:i + 4], retry=False))
    return good


def _json(items: list[str]) -> str:
    import json
    return json.dumps(items, ensure_ascii=False)
