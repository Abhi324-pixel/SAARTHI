// Turns the interface text of the whole page into Hindi or Hinglish.
//
// How it works: it reads the visible text on the page (and labels such as placeholders), asks the server for a translation of each
// sentence (cached there for everyone, and cached here in this browser), and swaps the words in place. Switching back to English puts
// the original text back. It never touches code, SQL, the learner's own writing (anything marked translate="no", text boxes, “quoted” text),
// numbers, links or e-mail addresses, and anything the server cannot translate safely simply stays in English.

import { req } from '../api'

type Lang = 'hindi' | 'hinglish'

const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'CODE', 'PRE', 'KBD', 'SAMP', 'TEXTAREA', 'INPUT', 'TITLE'])
const ATTRS = ['placeholder', 'aria-label', 'title', 'alt']
const DEVANAGARI = /[ऀ-ॿ]/
const BATCH = 40
const MAX_LEN = 400

function eligible(t: string): boolean {
  const s = t.trim()
  if (!s || s.length > MAX_LEN || !/[A-Za-z]{2}/.test(s) || DEVANAGARI.test(s)) return false
  if (/[“”]/.test(s)) return false                                  // verbatim quotes of what the learner said stay exactly as said
  if (/(https?:\/\/|www\.|@\w+\.\w+)/i.test(s)) return false
  return true
}

function blocked(el: Element | null): boolean {
  for (let e: Element | null = el; e; e = e.parentElement) {
    if (SKIP_TAGS.has(e.tagName.toUpperCase())) return true
    if (e.getAttribute('translate') === 'no' || e.hasAttribute('data-no-translate') || (e as HTMLElement).isContentEditable) return true
  }
  return false
}


// ALL-CAPS headings ("YOU ARE HERE") look like acronyms to a translator, so they are sent in normal case and shown in capitals again.
// All-caps code words (INNER JOIN, GROUP BY, HTTP) are left alone.
const CODE_WORDS = new Set(['SELECT', 'FROM', 'WHERE', 'JOIN', 'INNER', 'LEFT', 'RIGHT', 'OUTER', 'FULL', 'CROSS', 'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT',
  'OFFSET', 'NULL', 'AND', 'OR', 'NOT', 'IN', 'ON', 'AS', 'IS', 'LIKE', 'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'DISTINCT', 'INSERT', 'INTO', 'VALUES', 'UPDATE',
  'SET', 'DELETE', 'CREATE', 'TABLE', 'ALTER', 'DROP', 'INDEX', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'UNION', 'BETWEEN', 'EXISTS', 'PRIMARY', 'KEY',
  'FOREIGN', 'REFERENCES', 'HTTP', 'HTTPS', 'API', 'GET', 'POST', 'PUT', 'PATCH', 'REST', 'SQL', 'JSON', 'URL', 'CLI', 'GIT', 'CSS', 'HTML', 'ID', 'OK', 'AI', 'BKT', 'ACID', 'ORM'])

function capsHeading(core: string): boolean {
  if (core !== core.toUpperCase() || !/[A-Z]{2}/.test(core)) return false
  const words = core.match(/[A-Z]+/g) ?? []
  if (words.every(w => CODE_WORDS.has(w))) return false
  return words.length >= 2 || (words[0]?.length ?? 0) >= 5
}

function sendForm(core: string): { key: string; upper: boolean } {
  if (!capsHeading(core)) return { key: core, upper: false }
  const lower = core.toLowerCase()
  return { key: lower.charAt(0).toUpperCase() + lower.slice(1), upper: true }
}

interface Shown { orig: string; shown: string }

export class AutoTranslator {
  private lang: Lang | null = null
  private obs: MutationObserver | null = null
  private cache = new Map<string, string>()
  private misses = new Set<string>()          // sentences the server could not translate: do not ask again this session
  private pending = new Set<string>()
  private texts = new WeakMap<Text, Shown>()
  private attrs = new WeakMap<Element, Record<string, Shown>>()
  private tracked: WeakRef<Text>[] = []
  private trackedEls: WeakRef<Element>[] = []
  private timer: number | undefined
  private saveTimer: number | undefined
  private busy = false
  private pauseUntil = 0
  private known: Set<string> = new Set()
  root: HTMLElement | null = null

  start(lang: Lang, root: HTMLElement, known: Set<string>) {
    if (this.lang === lang && this.obs) return
    this.stop()
    this.lang = lang; this.root = root; this.known = known
    this.cache = new Map(); this.misses = new Set()
    try { const raw = localStorage.getItem(`saarthi.i18n.v2.${lang}`); if (raw) this.cache = new Map(Object.entries(JSON.parse(raw))) } catch { /* no saved copy */ }
    try {
      const at = Number(localStorage.getItem(`saarthi.i18n.v2.missAt.${lang}`) || 0)
      const raw = localStorage.getItem(`saarthi.i18n.v2.miss.${lang}`)
      if (raw && Date.now() - at < 24 * 3600 * 1000) this.misses = new Set(JSON.parse(raw))
    } catch { /* no saved copy */ }
    document.documentElement.lang = lang === 'hindi' ? 'hi' : 'hi-Latn'
    this.scan(root)
    this.obs = new MutationObserver(recs => this.onMutations(recs))
    this.obs.observe(root, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS })
  }

  stop() {
    this.obs?.disconnect(); this.obs = null
    window.clearTimeout(this.timer)
    if (this.lang) this.restore()
    this.lang = null; this.pending.clear()
    document.documentElement.lang = 'en'
  }

  private restore() {
    for (const w of this.tracked) { const n = w.deref(); const s = n && this.texts.get(n); if (n && s && n.nodeValue === s.shown) n.nodeValue = s.orig }
    for (const w of this.trackedEls) {
      const e = w.deref(); const m = e && this.attrs.get(e)
      if (e && m) for (const [a, s] of Object.entries(m)) if (e.getAttribute(a) === s.shown) e.setAttribute(a, s.orig)
    }
    this.tracked = []; this.trackedEls = []
  }

  private onMutations(recs: MutationRecord[]) {
    for (const r of recs) {
      if (r.type === 'characterData') this.consider(r.target as Text)
      else if (r.type === 'attributes') this.considerAttr(r.target as Element, r.attributeName!)
      else r.addedNodes.forEach(n => { if (n.nodeType === Node.TEXT_NODE) this.consider(n as Text); else if (n.nodeType === Node.ELEMENT_NODE) this.scan(n as Element) })
    }
    this.schedule()
  }

  private scan(el: Element) {
    if (blocked(el.parentElement) || blocked(el)) return
    const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT)
    for (let n = w.nextNode(); n; n = w.nextNode()) this.consider(n as Text)
    el.querySelectorAll('*').forEach(e => { for (const a of ATTRS) if (e.hasAttribute(a)) this.considerAttr(e, a) })
    for (const a of ATTRS) if (el.hasAttribute(a)) this.considerAttr(el, a)
    this.schedule()
  }

  private lookup(core: string): string | undefined {
    if (this.known.has(core)) return undefined
    const { key, upper } = sendForm(core)
    const tr = this.cache.get(key)
    return tr === undefined ? undefined : (upper ? tr.toUpperCase() : tr)
  }

  private queue(core: string) {
    if (this.known.has(core)) return
    const { key } = sendForm(core)
    if (!this.misses.has(key)) this.pending.add(key)
  }

  private consider(node: Text) {
    const v = node.nodeValue ?? ''
    const st = this.texts.get(node)
    if (st && st.shown === v) return                                  // this is our own translation
    if (blocked(node.parentElement) || !eligible(v)) return
    const core = v.trim()
    const tr = this.lookup(core)
    if (tr !== undefined) {
      const lead = v.slice(0, v.indexOf(core)), trail = v.slice(v.indexOf(core) + core.length)
      const shown = lead + tr + trail
      this.texts.set(node, { orig: v, shown })
      if (!st) this.tracked.push(new WeakRef(node))
      node.nodeValue = shown
    } else this.queue(core)
  }

  private considerAttr(el: Element, a: string) {
    const v = el.getAttribute(a) ?? ''
    const map = this.attrs.get(el) ?? {}
    if (map[a] && map[a].shown === v) return
    if (blocked(el) || !eligible(v)) return
    const tr = this.lookup(v.trim())
    if (tr !== undefined) {
      map[a] = { orig: v, shown: tr }
      if (!this.attrs.has(el)) this.trackedEls.push(new WeakRef(el))
      this.attrs.set(el, map)
      el.setAttribute(a, tr)
    } else this.queue(v.trim())
  }

  private schedule() {
    if (!this.pending.size) return
    window.clearTimeout(this.timer)
    this.timer = window.setTimeout(() => this.flush(), 150)
  }

  private async flush() {
    if (this.busy || !this.lang || Date.now() < this.pauseUntil) { if (this.pending.size) this.timer = window.setTimeout(() => this.flush(), 1500); return }
    this.busy = true
    const lang = this.lang
    try {
      while (this.pending.size && this.lang === lang) {
        const batches: string[][] = []                                  // up to three requests at once: the first view of a page has many sentences
        for (let i = 0; i < 3 && this.pending.size; i++) {
          const b = [...this.pending].slice(0, BATCH)
          b.forEach(x => this.pending.delete(x))
          batches.push(b)
        }
        const results = await Promise.all(batches.map(b =>
          req('/i18n/translate', { body: { lang, texts: b } }).then((r: { translations: (string | null)[] }) => ({ b, r })).catch(() => ({ b, r: null }))))
        if (this.lang !== lang) return
        let failed = false
        for (const { b, r } of results) {
          if (!r) { failed = true; b.forEach(x => this.pending.add(x)); continue }
          b.forEach((src, i) => { const tr = r.translations?.[i]; if (tr) this.cache.set(src, tr); else this.misses.add(src) })
        }
        if (this.root) this.scan(this.root)
        this.persist()
        if (failed) { this.pauseUntil = Date.now() + 20000; break }      // server busy or offline: stay in English for now, try again
      }
    } catch { /* unexpected problem: the finally block schedules another try */ }
    finally {
      this.busy = false
      if (this.pending.size && this.lang === lang) this.timer = window.setTimeout(() => this.flush(), Math.max(500, this.pauseUntil - Date.now()))
    }
  }

  private persist() {
    window.clearTimeout(this.saveTimer)
    this.saveTimer = window.setTimeout(() => {
      if (!this.lang) return
      try {
        const entries = [...this.cache.entries()].slice(-3000)
        localStorage.setItem(`saarthi.i18n.v2.${this.lang}`, JSON.stringify(Object.fromEntries(entries)))
        localStorage.setItem(`saarthi.i18n.v2.miss.${this.lang}`, JSON.stringify([...this.misses].slice(-2000)))
        if (!localStorage.getItem(`saarthi.i18n.v2.missAt.${this.lang}`) || this.misses.size === 0) localStorage.setItem(`saarthi.i18n.v2.missAt.${this.lang}`, String(Date.now()))
      } catch { /* storage full or blocked: translations still work for this visit */ }
    }, 800)
  }
}

export const translator = new AutoTranslator()
