import { useEffect } from 'react'
import { translator } from '../lib/autoTranslate'
import { knownUiTexts, useApp } from '../store'

/** Switches the page-wide translator on for Hindi and Hinglish and off for English. Renders nothing. */
export default function AutoTranslate() {
  const { lang } = useApp()
  useEffect(() => {
    const root = document.getElementById('root')
    if (!root) return
    if (lang === 'english') translator.stop()
    else translator.start(lang, root, knownUiTexts(lang))
  }, [lang])
  return null
}
