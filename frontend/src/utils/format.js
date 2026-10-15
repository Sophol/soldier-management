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

// decision workflow (backend core/permissions.py): draft -> 6 approval levels -> approved -> published
export const WORKFLOW = [
  { status: 'draft', step: '១. ចុះបញ្ជីសំណើ', label: 'ព្រាង' },
  { status: 'review', step: '២. មន្ត្រីជំនាញ', label: 'ពិនិត្យលក្ខខណ្ឌ' },
  { status: 'deputy_office', step: '៣. នាយរងការិយាល័យ', label: 'រង់ចាំនាយរងការិយាល័យ' },
  { status: 'chief_office', step: '៤. ប្រធានការិយាល័យ', label: 'រង់ចាំប្រធានការិយាល័យ' },
  { status: 'deputy_department', step: '៥. នាយរងនាយកដ្ឋាន', label: 'រង់ចាំនាយរងនាយកដ្ឋាន' },
  { status: 'director', step: '៦. នាយកដ្ឋាន', label: 'រង់ចាំនាយកដ្ឋាន' },
  { status: 'leadership', step: '៧. ថ្នាក់ដឹកនាំកំពូល', label: 'រង់ចាំថ្នាក់ដឹកនាំកំពូល' },
  { status: 'approved', step: '៨. ចេញលិខិត', label: 'បានអនុម័ត (រង់ចាំចេញលិខិត)' },
  { status: 'published', step: 'បានផ្សព្វផ្សាយ', label: 'បានផ្សព្វផ្សាយ' },
]
export const STATUS_TEXT = {
  ...Object.fromEntries(WORKFLOW.map((w) => [w.status, w.label])), rejected: 'បានបដិសេធ', cancelled: 'បានលុបចោល',
}
export const STATUS_TAG = Object.fromEntries(Object.keys(STATUS_TEXT).map((k) => [k,
  { draft: 'info', approved: 'success', published: 'success', rejected: 'danger', cancelled: 'danger' }[k] || 'warning']))

/** Today as yyyy-mm-dd in the browser's time zone (toISOString() is UTC: before 07:00 in Cambodia it gives yesterday). */
export function todayISO() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
