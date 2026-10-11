import { createI18n } from 'vue-i18n'
import km from './km'
import en from './en'

let locale = 'km'
try { locale = localStorage.getItem('locale') || 'km' } catch { /* ignore */ }

export const i18n = createI18n({ legacy: false, locale, fallbackLocale: 'km', messages: { km, en } })

export function setLocale(l) {
  i18n.global.locale.value = l
  try { localStorage.setItem('locale', l) } catch { /* ignore */ }
  document.documentElement.lang = l
}
