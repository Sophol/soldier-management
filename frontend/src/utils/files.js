export const ACCEPT = '.pdf,.jpg,.jpeg,.png,.gif,.webp,.doc,.docx,.xls,.xlsx'

const ext = (name = '') => name.split('.').pop().toLowerCase()

export function fileKind(name) {
  const e = ext(name)
  if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(e)) return 'image'
  if (e === 'pdf') return 'pdf'
  if (['doc', 'docx'].includes(e)) return 'word'
  if (['xls', 'xlsx'].includes(e)) return 'excel'
  return 'other'
}

export const KIND_ICON = { image: 'Picture', pdf: 'Document', word: 'Notebook', excel: 'Grid', other: 'Files' }
export const KIND_COLOR = { image: '#4f7cac', pdf: '#c0392b', word: '#2b5797', excel: '#1e7145', other: '#6b7785' }
