import http from '@/api/http'

const PRINT_KEY = 'list_print'
const MAX_ROWS = 20000

/** Every row of a paged list endpoint for the given filter (pages of `pageSize`). */
export async function fetchAll(endpoint, params, pageSize = 200) {
  const items = []
  for (let page = 1; ; page++) {
    const { data } = await http.get(endpoint, { params: { ...params, page, size: pageSize } })
    items.push(...data.items)
    if (items.length >= data.total || !data.items.length || items.length >= MAX_ROWS) return items
  }
}

/** Excel of the rows as shown on screen. columns: [{ label, text(row) }] */
export async function exportExcel(module, title, columns, rows) {
  const body = { module, title, columns: columns.map((c) => c.label), rows: rows.map((r) => columns.map((c) => c.text(r) ?? '')) }
  const res = await http.post('/export/table', body, { responseType: 'blob' })
  const href = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = href
  a.download = `${title}.xlsx`
  a.click()
  setTimeout(() => URL.revokeObjectURL(href), 1000)
}

/** Opens the printable A4 list (print or save as PDF from the browser) with the rows as shown on screen. */
export function printList(router, title, subtitle, columns, rows) {
  const data = { title, subtitle, columns: columns.map((c) => c.label), rows: rows.map((r) => columns.map((c) => String(c.text(r) ?? ''))) }
  try { sessionStorage.setItem(PRINT_KEY, JSON.stringify(data)) } catch { /* too large for the session: print what fits */ }
  router.push('/print/list')
}

export function printedList() {
  try { return JSON.parse(sessionStorage.getItem(PRINT_KEY)) } catch { return null }
}

/** "label: value" text of the filters in use, printed under the title. */
export function filterSummary(parts) {
  return parts.filter(([, v]) => v !== null && v !== undefined && v !== '').map(([k, v]) => `${k}: ${v}`).join(' • ')
}
