const KH_DIGITS = '០១២៣៤៥៦៧៨៩'
const KH_MONTHS = ['មករា', 'កុម្ភៈ', 'មីនា', 'មេសា', 'ឧសភា', 'មិថុនា', 'កក្កដា', 'សីហា', 'កញ្ញា', 'តុលា', 'វិច្ឆិកា', 'ធ្នូ']

export const prefs = {
  get khmerDigits() {
    try { return localStorage.getItem('khmer_digits') === '1' } catch { return false }
  },
  set khmerDigits(v) {
    try { localStorage.setItem('khmer_digits', v ? '1' : '0') } catch { /* ignore */ }
  },
}

export function khDigits(value) {
  if (value == null) return ''
  return String(value).replace(/[0-9]/g, (d) => KH_DIGITS[d])
}

export function num(value) {
  if (value == null || value === '') return ''
  return prefs.khmerDigits ? khDigits(value) : String(value)
}

/** yyyy-mm-dd -> dd/mm/yyyy */
export function fmtDate(value) {
  if (!value) return ''
  const [y, m, d] = String(value).slice(0, 10).split('-')
  return num(`${d}/${m}/${y}`)
}

/** yyyy-mm-dd -> ថ្ងៃទី dd ខែ ... ឆ្នាំ yyyy (official style, Khmer digits) */
export function fmtDateLong(value) {
  if (!value) return ''
  const [y, m, d] = String(value).slice(0, 10).split('-')
  return `ថ្ងៃទី${khDigits(d)} ខែ${KH_MONTHS[Number(m) - 1]} ឆ្នាំ${khDigits(y)}`
}

export function fmtDateTime(value) {
  if (!value) return ''
  return `${fmtDate(value)} ${num(String(value).slice(11, 16))}`
}

export function genderText(g) {
  return g === 'M' ? 'ប្រុស' : g === 'F' ? 'ស្រី' : ''
}

export function fileSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

export const STATUS_TAG = { draft: 'info', approved: 'success', cancelled: 'danger' }
export const STATUS_TEXT = { draft: 'ព្រាង', approved: 'បានអនុម័ត', cancelled: 'បានលុបចោល' }
