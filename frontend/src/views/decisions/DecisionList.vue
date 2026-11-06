<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import http, { download, downloadPost } from '@/api/http'
import { useAuth } from '@/stores/auth'
import { useLookups } from '@/stores/lookups'
import SoldierSelect from '@/components/SoldierSelect.vue'
import UnitTreeSelect from '@/components/UnitTreeSelect.vue'
import FileAttachments from '@/components/FileAttachments.vue'
import DocumentSelect from '@/components/DocumentSelect.vue'
import SavedFilters from '@/components/SavedFilters.vue'
import { STATUS_TAG, STATUS_TEXT, WORKFLOW, fmtDate, fmtDateTime, num, todayISO } from '@/utils/format'
import { exportExcel, fetchAll, filterSummary, printList } from '@/utils/listExport'

const route = useRoute()
const router = useRouter()
const auth = useAuth()
const lookups = useLookups()
const kind = computed(() => route.params.kind)
const module = computed(() => `decisions_${kind.value}`)
const TITLES = { appoint: 'តែងតាំងមុខតំណែង', transfer: 'ផ្លាស់ប្ដូរមុខតំណែង / កងឯកភាព និងដំឡើងឋានន្តរស័ក្តិ', promote: 'ដំឡើងឋានន្តរស័ក្តិ' }

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const blank = {
  q: '', status: null, date_from: null, date_to: null, effective_from: null, effective_to: null, waiting: false, overdue: false,
  old_rank_id: null, new_rank_id: null, old_position_id: null, new_position_id: null, old_unit_id: null, new_unit_id: null,
  institution_id: null, created_by: null, created_from: null, created_to: null,
}
const q = reactive({ page: 1, size: 20, ...blank })
// filters can come from the URL (dashboard links, bookmarks)
for (const [k, v] of Object.entries(route.query)) {
  if (!(k in blank) || v === '') continue
  q[k] = typeof blank[k] === 'boolean' ? v === 'true' : /^\d+$/.test(v) && k.endsWith('_id') || k === 'created_by' ? Number(v) : v
}
const showMore = ref(Object.keys(route.query).some((k) => !['q', 'status', 'waiting', 'institution_id'].includes(k) && k in blank))
// ស្ថាប័នកងឯកភាព = the top-level units; a unit belongs to the one at the start of its path ("/3/12/")
const institutions = computed(() => lookups.unitTree.filter((u) => u.level === 1))
const institutionOf = (unitId) => Number(lookups.unitMap[unitId]?.path?.split('/')[1]) || null
const users = ref([])
const exporting = ref(false)
const range = (from, to) => computed({
  get: () => (q[from] || q[to] ? [q[from], q[to]] : null),
  set: (v) => { q[from] = v?.[0] || null; q[to] = v?.[1] || null },
})
const decisionDates = range('date_from', 'date_to')
const effectiveDates = range('effective_from', 'effective_to')
const createdDates = range('created_from', 'created_to')
watch(showMore, async (v) => { if (v && !users.value.length) users.value = await lookups.loadUsers() }, { immediate: true })

function filterValues() {
  const out = {}
  for (const k of Object.keys(blank)) if (q[k] !== null && q[k] !== '' && q[k] !== false) out[k] = q[k]
  return out
}
function search() {
  q.page = 1
  router.replace({ query: filterValues() })
  load()
}
function resetFilters() { Object.assign(q, blank); search() }
function applySaved(values) {
  Object.assign(q, blank, values)
  showMore.value = true
  search()
}

const dialog = ref(false)
const saving = ref(false)
const form = ref({})
const formRef = ref()
const detail = ref(null)
// ព័ត៌មានខុសប្រក្រតី: about the decision itself (dates) above the table, and per soldier next to the new unit
const warnings = ref([])
const itemWarnings = ref({}) // soldier_id -> [messages]
// what saving would refuse (missing choice, lower rank, full staffing slot / rank quota...), shown in the same place
const itemErrors = ref({}) // soldier_id -> [messages]
const warnedCount = computed(() => form.value.items?.filter((i) => itemWarnings.value[i.soldier_id]?.length).length || 0)
const errorCount = computed(() => form.value.items?.filter((i) => itemErrors.value[i.soldier_id]?.length).length || 0)
function setWarnings(general, items) {
  warnings.value = general || []
  itemWarnings.value = Object.fromEntries((items || []).map((i) => [i.soldier_id, i.warnings ?? i.anomalies ?? []]))
  itemErrors.value = Object.fromEntries((items || []).map((i) => [i.soldier_id, i.errors ?? []]))
}
const warnRow = ({ row }) => (itemErrors.value[row.soldier_id]?.length ? 'error-row'
  : itemWarnings.value[row.soldier_id]?.length ? 'warn-row' : '')
// anomalies are checked only while the decision can still change something (the server sends none afterwards)
const anomaliesChecked = (d) => WORKFLOW.slice(0, -1).some((w) => w.status === d.status)
const detailWarned = computed(() => detail.value?.items.filter((i) => i.anomalies?.length).length || 0)

// the decision number is usually known only once signed: it can be left empty and given when publishing
const rules = {
  decision_date: [{ required: true, message: 'សូមបញ្ចូលថ្ងៃខែឆ្នាំ' }],
  effective_date: [{ required: true, message: 'សូមបញ្ចូលថ្ងៃចូលជាធរមាន' }],
}

async function load() {
  loading.value = true
  try {
    const params = { kind: kind.value, page: q.page, size: q.size, ...filterValues() }
    const { data } = await http.get('/decisions', { params })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function emptyItem() {
  return { soldier_id: null, soldier: null, new_rank_id: null, new_position_id: null, new_institution_id: null, new_unit_id: null, note: '' }
}

// choosing a ស្ថាប័នកងឯកភាព moves the soldier to it, unless the chosen unit is already inside it
function setInstitution(row, id) {
  row.new_institution_id = id
  if (!id) row.new_unit_id = null
  else if (institutionOf(row.new_unit_id) !== id) row.new_unit_id = id
}
function setUnit(row, id) {
  row.new_unit_id = id
  if (id) row.new_institution_id = institutionOf(id)
}

function openCreate() {
  clearStaffing()
  const today = todayISO()
  form.value = {
    id: null, decision_no: '', decision_date: today, effective_date: today, issued_by: '', notes: '',
    incoming_document_id: null, incoming_label: '', items: [emptyItem()],
  }
  setWarnings([], [])
  dialog.value = true
}

async function openEdit(row) {
  clearStaffing()
  const { data } = await http.get(`/decisions/${row.id}`)
  form.value = {
    id: data.id, decision_no: data.decision_no, decision_date: data.decision_date, effective_date: data.effective_date,
    issued_by: data.issued_by, notes: data.notes,
    incoming_document_id: data.incoming_document_id, incoming_label: data.incoming_no || '',
    items: data.items.map((i) => ({
      soldier_id: i.soldier_id,
      soldier: {
        rank_name: i.old_rank, position_name: i.old_position, unit_name: i.old_unit, institution_name: i.old_institution,
        unit_id: i.old_unit_id,
        rank_sort: lookups.list('ranks').find((r) => r.id === i.old_rank_id)?.sort_order, // keeps the "higher rank only" filter
      },
      label: `${i.old_rank || ''} ${i.name_kh} (${i.military_id})`, new_rank_id: i.new_rank_id,
      new_position_id: i.new_position_id, new_institution_id: institutionOf(i.new_unit_id), new_unit_id: i.new_unit_id, note: i.note,
    })),
  }
  setWarnings(data.general_anomalies, data.items)
  dialog.value = true
}

// a rejected or cancelled decision as a new draft: the same soldiers and changes, with the soldiers' current records
async function openCopy(row) {
  clearStaffing()
  const { data } = await http.get(`/decisions/${row.id}`)
  const fresh = await Promise.all(data.items.map((i) => http.get(`/soldiers/${i.soldier_id}`, { silent: true })
    .then((r) => r.data).catch(() => null)))
  const today = todayISO()
  form.value = {
    id: null, decision_no: '', decision_date: today, effective_date: data.effective_date > today ? data.effective_date : today,
    issued_by: data.issued_by, incoming_document_id: data.incoming_document_id, incoming_label: data.incoming_no || '',
    notes: [data.notes, `ចម្លងពីសេចក្ដីសម្រេច${data.decision_no ? ` លេខ ${data.decision_no}` : ''} (${STATUS_TEXT[data.status]})`]
      .filter(Boolean).join('\n'),
    items: data.items.map((i, n) => {
      const sol = fresh[n]
      return {
        soldier_id: i.soldier_id, soldier: sol,
        label: sol ? `${sol.rank_name || ''} ${sol.name_kh} (${sol.military_id})`.trim() : `${i.name_kh} (${i.military_id})`,
        new_rank_id: i.new_rank_id, new_position_id: i.new_position_id, new_institution_id: institutionOf(i.new_unit_id),
        new_unit_id: i.new_unit_id, note: i.note,
      }
    }),
  }
  setWarnings([], [])
  detail.value = null
  dialog.value = true
}
const canCopy = (d) => ['rejected', 'cancelled'].includes(d.status) && auth.can(`${module.value}.create`)

// ក្របខណ្ឌទំនេរ: the staffing table of the unit each soldier goes to (or stays in), shown while choosing the position
const staffing = reactive({}) // unit_id -> { position_id: staffing row } ({} = no staffing table, null = loading)
// the table changes as decisions are approved: read it again each time a form opens
function clearStaffing() { for (const k of Object.keys(staffing)) delete staffing[k] }
async function loadStaffing(unitId) {
  if (!unitId || unitId in staffing) return
  staffing[unitId] = null
  try {
    const { data } = await http.get('/unit-positions', { params: { unit_id: unitId, size: 1000 }, silent: true })
    staffing[unitId] = Object.fromEntries(data.items.map((r) => [r.position_id, r]))
  } catch {
    staffing[unitId] = {} // no permission to see the staffing table: plain list
  }
}
const targetUnit = (row) => row.new_unit_id || row.soldier?.unit_id || null
watch(() => dialog.value && form.value.items?.map(targetUnit), (ids) => { if (ids) ids.forEach(loadStaffing) }, { deep: true })
function positionOptions(row) {
  const all = lookups.list('positions')
  const table = staffing[targetUnit(row)]
  if (!table || !Object.keys(table).length) return all.map((p) => ({ ...p, slot: null, outside: false }))
  // the unit's staffing table first, most vacancies first; then the positions outside it (saving refuses them)
  const inTable = all.filter((p) => table[p.id]).map((p) => ({ ...p, slot: table[p.id], outside: false }))
    .sort((a, b) => b.slot.vacant - a.slot.vacant)
  return [...inTable, ...all.filter((p) => !table[p.id]).map((p) => ({ ...p, slot: null, outside: true }))]
}

// the form as the API takes it (save, live check and the Excel of the form use the same body)
function formPayload() {
  return {
    kind: kind.value, decision_no: form.value.decision_no, decision_date: form.value.decision_date,
    effective_date: form.value.effective_date, issued_by: form.value.issued_by, notes: form.value.notes,
    incoming_document_id: form.value.incoming_document_id,
    items: form.value.items.filter((i) => i.soldier_id)
      .map(({ soldier_id, new_rank_id, new_position_id, new_unit_id, note }) => ({ soldier_id, new_rank_id, new_position_id, new_unit_id, note })),
  }
}

async function save() {
  await formRef.value.validate()
  const payload = formPayload()
  if (!payload.items.length) return ElMessage.warning('សូមបន្ថែមយោធិនយ៉ាងហោចណាស់ម្នាក់')
  saving.value = true
  try {
    const { data } = form.value.id ? await http.put(`/decisions/${form.value.id}`, payload) : await http.post('/decisions', payload)
    if (data.warnings?.length) {
      setWarnings(data.general_anomalies, data.items)
      ElMessage.warning('បានរក្សាទុក ប៉ុន្តែមានព័ត៌មានខុសប្រក្រតី (មើលខាងលើតារាង និងនៅជាប់អង្គភាពថ្មីរបស់យោធិនម្នាក់ៗ)')
      form.value.id = data.id
    } else {
      ElMessage.success('បានរក្សាទុកជាសេចក្ដីព្រាង')
      dialog.value = false
    }
    load()
  } finally {
    saving.value = false
  }
}

// ព័ត៌មានខុសប្រក្រតី: re-checked on the server while the form is typed (warnings never block saving)
let checkTimer = null
let checkSeq = 0
watch(() => dialog.value && [form.value.decision_no, form.value.decision_date, form.value.effective_date, form.value.incoming_document_id,
  form.value.items?.map((i) => [i.soldier_id, i.new_rank_id, i.new_position_id, i.new_unit_id])], (on) => {
  clearTimeout(checkTimer)
  if (!on) return
  checkTimer = setTimeout(async () => {
    const seq = ++checkSeq
    try {
      const { data } = await http.post('/decisions/check', { id: form.value.id, ...formPayload() }, { silent: true })
      if (seq === checkSeq) setWarnings(data.general ?? data.warnings, data.items)
    } catch { /* a failed check only means no warnings are shown; saving still validates */ }
  }, 400)
}, { deep: true })

// the proposal as it stands in the form (saved or not) as an Excel file, with each soldier's anomalies and errors
async function exportForm() {
  const payload = formPayload()
  if (!payload.items.length) return ElMessage.warning('សូមបន្ថែមយោធិនយ៉ាងហោចណាស់ម្នាក់')
  downloading.value = true
  try {
    await downloadPost('/decisions/export-preview', { id: form.value.id, ...payload }, `decision-${kind.value}.xlsx`)
  } finally {
    downloading.value = false
  }
}

async function showDetail(row) {
  detail.value = (await http.get(`/decisions/${row.id}`)).data
}

// the proposal (សំណើ) as an Excel file: details and one row per soldier, with each soldier's anomalies
const downloading = ref(false)
async function exportDecision(d) {
  downloading.value = true
  try {
    await download(`/decisions/${d.id}/export`, {}, `decision-${d.id}.xlsx`)
  } finally {
    downloading.value = false
  }
}

// workflow buttons: the server sends the actions this user may do now (row.actions)
const ACTIONS = {
  submit: { label: 'ដាក់ជូន', type: 'primary', icon: 'Promotion', confirm: 'ដាក់សំណុំរឿងនេះជូននាយរងការិយាល័យ (ទទួលទិស)?' },
  approve: { label: 'អនុម័ត', type: 'success', icon: 'Select', prompt: 'មតិ (ស្រេចចិត្ត)' },
  return: { label: 'ត្រឡប់ទៅកែ', type: 'warning', icon: 'Back', prompt: 'មូលហេតុដែលត្រឡប់ទៅកែ', required: true },
  reject: { label: 'បដិសេធ', type: 'danger', icon: 'CircleClose', prompt: 'មូលហេតុនៃការបដិសេធ', required: true },
  cancel: { label: 'លុបចោល', type: 'danger', icon: 'RefreshLeft', confirm: 'លុបចោលសេចក្ដីសម្រេចដែលបានអនុម័ត? ព័ត៌មានយោធិននឹងត្រឡប់ទៅដូចមុនវិញ។' },
}
const workflowActions = (d) => (d.actions || []).filter((a) => ACTIONS[a])

// Export Excel / PDF of every decision matching the filter
const EXPORT_COLUMNS = [
  { label: 'លេខសេចក្ដីសម្រេច', text: (r) => r.decision_no },
  { label: 'ថ្ងៃខែឆ្នាំ', text: (r) => fmtDate(r.decision_date) },
  { label: 'ចូលជាធរមាន', text: (r) => fmtDate(r.effective_date) },
  { label: 'ចំនួនយោធិន', text: (r) => r.item_count },
  { label: 'ស្ថាប័នកងឯកភាព', text: (r) => r.institutions.join(', ') },
  { label: 'ចេញដោយ', text: (r) => r.issued_by },
  { label: 'អ្នកដាក់សំណើ', text: (r) => r.created_by_name },
  { label: 'ស្ថានភាព', text: (r) => STATUS_TEXT[r.status] + (r.pending ? ' (រង់ចាំថ្ងៃចូលជាធរមាន)' : '') + (r.overdue ? ' (យឺតយ៉ាវ)' : '') },
  { label: 'ព័ត៌មានខុសប្រក្រតី', text: (r) => r.anomalies.join('\n') },
  { label: 'កំណត់សម្គាល់', text: (r) => r.notes },
]
function filterText() {
  const name = (key, id) => lookups.name(key, id)
  return filterSummary([
    ['ពាក្យគន្លឹះ', q.q], ['ស្ថាប័នកងឯកភាព', lookups.unitMap[q.institution_id]?.name_kh], ['ស្ថានភាព', STATUS_TEXT[q.status]], ['រង់ចាំខ្ញុំ', q.waiting ? 'បាទ' : ''], ['យឺតយ៉ាវ', q.overdue ? 'បាទ' : ''],
    ['ថ្ងៃសម្រេច', q.date_from || q.date_to ? `${fmtDate(q.date_from)} → ${fmtDate(q.date_to)}` : ''],
    ['ចូលជាធរមាន', q.effective_from || q.effective_to ? `${fmtDate(q.effective_from)} → ${fmtDate(q.effective_to)}` : ''],
    ['ស័ក្តិចាស់', name('ranks', q.old_rank_id)], ['ស័ក្តិថ្មី', name('ranks', q.new_rank_id)],
    ['តំណែងចាស់', name('positions', q.old_position_id)], ['តំណែងថ្មី', name('positions', q.new_position_id)],
    ['អង្គភាពចាស់', lookups.unitMap[q.old_unit_id]?.name_kh], ['អង្គភាពថ្មី', lookups.unitMap[q.new_unit_id]?.name_kh],
    ['អ្នកដាក់សំណើ', users.value.find((u) => u.id === q.created_by)?.full_name],
  ])
}
async function exportAs(kindOfFile) {
  exporting.value = true
  try {
    const all = await fetchAll('/decisions', { kind: kind.value, ...filterValues() })
    if (kindOfFile === 'xlsx') await exportExcel(module.value, TITLES[kind.value], EXPORT_COLUMNS, all)
    else printList(router, `សេចក្ដីសម្រេច${TITLES[kind.value]}`, filterText(), EXPORT_COLUMNS, all)
  } finally {
    exporting.value = false
  }
}

async function act(row, action) {
  const m = ACTIONS[action]
  // the director's approval is final: it registers the letter and updates the records
  if (action === 'approve' && row.status === 'submitted') return openPublish(row)
  // sending on or approving a decision with anomalies: the user confirms having seen them
  if (['submit', 'approve'].includes(action) && row.anomalies?.length) {
    await ElMessageBox.confirm(
      `សេចក្ដីសម្រេចនេះមានព័ត៌មានខុសប្រក្រតី ${num(row.anomalies.length)}៖\n\n${row.anomalies.map((a) => `• ${a}`).join('\n')}\n\nនៅតែ${m.label}?`,
      'ព័ត៌មានខុសប្រក្រតី', { type: 'warning', confirmButtonText: m.label, cancelButtonText: 'បោះបង់', customClass: 'pre-line-box' })
    if (m.confirm) {
      await http.post(`/decisions/${row.id}/${action}`, { comment: null })
      ElMessage.success('រួចរាល់')
      return afterAction(row)
    }
  }
  let comment = null
  if (action === 'cancel') {
    const { value } = await ElMessageBox.prompt(row.pending
      ? 'លុបចោលសេចក្ដីសម្រេចនេះ? វាមិនទាន់ចូលជាធរមាន ដូច្នេះព័ត៌មានយោធិនមិនទាន់ផ្លាស់ប្ដូរទេ។ លិខិតចេញនឹងត្រូវកត់ថាលុបចោល។\n\nមូលហេតុ (ស្រេចចិត្ត)'
      : 'លុបចោលសេចក្ដីសម្រេចដែលបានអនុម័ត? ព័ត៌មានយោធិននឹងត្រឡប់ទៅដូចមុនវិញ ហើយលិខិតចេញនឹងត្រូវកត់ថាលុបចោល។\n\nមូលហេតុ (ស្រេចចិត្ត)',
    m.label, { type: 'warning', inputType: 'textarea', confirmButtonText: m.label, cancelButtonText: 'បោះបង់', customClass: 'pre-line-box' })
    comment = value?.trim() || null
  } else if (m.prompt) {
    const { value } = await ElMessageBox.prompt(m.prompt, m.label, {
      inputType: 'textarea', confirmButtonText: m.label, cancelButtonText: 'បោះបង់',
      inputValidator: (v) => !m.required || !!v?.trim() || 'សូមបញ្ចូលមូលហេតុ',
    })
    comment = value?.trim() || null
  } else {
    await ElMessageBox.confirm(m.confirm, m.label, { type: 'warning', confirmButtonText: m.label, cancelButtonText: 'បោះបង់' })
  }
  await http.post(`/decisions/${row.id}/${action}`, { comment })
  ElMessage.success('រួចរាល់')
  await afterAction(row)
}

async function afterAction(row) {
  if (detail.value?.id === row.id) detail.value = (await http.get(`/decisions/${row.id}`)).data
  load()
}

// final approval by the director: register the outgoing letter (number given now or allocated) and update the records
const publishing = ref(null)
function openPublish(row) {
  publishing.value = { row, decision_no: row.decision_no || '', decision_date: row.decision_date, comment: '' }
}
async function publish() {
  const { row, decision_no, decision_date } = publishing.value
  saving.value = true
  try {
    await http.post(`/decisions/${row.id}/approve`, { decision_no: decision_no || null, decision_date, comment: publishing.value.comment || null })
    ElMessage.success(row.effective_date > todayISO()
      ? `បានអនុម័ត — ព័ត៌មានយោធិននឹងត្រូវធ្វើបច្ចុប្បន្នភាពនៅថ្ងៃចូលជាធរមាន ${fmtDate(row.effective_date)}`
      : 'បានអនុម័ត ហើយព័ត៌មានយោធិនត្រូវបានធ្វើបច្ចុប្បន្នភាព')
    publishing.value = null
    await afterAction(row)
  } finally {
    saving.value = false
  }
}

const stepIndex = (status) => WORKFLOW.findIndex((w) => w.status === status)
const STEP_ACTION = { submit: 'ដាក់ជូន', approve: 'អនុម័ត', return: 'ត្រឡប់ទៅកែ', reject: 'បដិសេធ', publish: 'ផ្សព្វផ្សាយ', cancel: 'លុបចោល', // publish: older logs
  apply: 'ចូលជាធរមាន (បានធ្វើបច្ចុប្បន្នភាពយោធិន)', apply_failed: 'មិនអាចអនុវត្តនៅថ្ងៃចូលជាធរមាន' }
const STEP_TYPE = { approve: 'success', publish: 'success', apply: 'success', return: 'warning', reject: 'danger', cancel: 'danger', apply_failed: 'danger', submit: 'primary' }

async function remove(row) {
  await ElMessageBox.confirm('លុបសេចក្ដីព្រាងនេះ?', 'បញ្ជាក់', { type: 'warning' })
  await http.delete(`/decisions/${row.id}`)
  load()
}

// a transfer may also promote (ផ្លាស់ប្ដូរមុខតំណែង និងដំឡើងឋានន្តរស័ក្តិ); the new rank is optional there
const showRank = computed(() => kind.value !== 'appoint')
const showPosition = computed(() => kind.value !== 'promote')
const showUnit = computed(() => kind.value !== 'promote')

function rankOptions(item) {
  const cur = item.soldier?.rank_sort
  return lookups.list('ranks').filter((r) => cur == null || r.sort_order > cur)
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h2>{{ TITLES[kind] }}</h2>
      <div class="head-actions">
        <SavedFilters :module="`decisions/${kind}`" :current="filterValues" @apply="applySaved" />
        <el-button v-if="auth.can(`${module}.export`)" icon="Download" :loading="exporting" @click="exportAs('xlsx')">នាំចេញ Excel</el-button>
        <el-button v-if="auth.can(`${module}.print`)" icon="Printer" :loading="exporting" @click="exportAs('pdf')">បោះពុម្ព / PDF</el-button>
        <el-button v-if="auth.can(`${module}.create`)" type="primary" icon="Plus" @click="openCreate">បង្កើតសេចក្ដីសម្រេចថ្មី</el-button>
      </div>
    </div>

    <el-card shadow="never" class="filter-card">
      <el-form inline @submit.prevent="search">
        <el-form-item><el-input v-model="q.q" placeholder="លេខ / ឈ្មោះ / អត្តលេខ" clearable prefix-icon="Search" /></el-form-item>
        <el-form-item label="ស្ថាប័នកងឯកភាព">
          <el-select v-model="q.institution_id" clearable filterable style="width: 220px" @change="search">
            <el-option v-for="u in institutions" :key="u.id" :value="u.id" :label="u.name_kh" />
          </el-select>
        </el-form-item>
        <el-form-item label="ស្ថានភាព / ជំហានអនុម័ត">
          <el-select v-model="q.status" clearable style="width: 240px">
            <el-option v-for="(t, k) in STATUS_TEXT" :key="k" :value="k" :label="t" />
          </el-select>
        </el-form-item>
        <el-form-item><el-checkbox v-model="q.waiting" @change="search">រង់ចាំខ្ញុំអនុម័ត</el-checkbox></el-form-item>
        <el-form-item><el-checkbox v-model="q.overdue" @change="search">យឺតយ៉ាវ</el-checkbox></el-form-item>
        <el-form-item label="ថ្ងៃសម្រេច">
          <el-date-picker v-model="decisionDates" type="daterange" value-format="YYYY-MM-DD" format="DD/MM/YYYY" start-placeholder="ពីថ្ងៃ" end-placeholder="ដល់ថ្ងៃ" style="width: 260px" />
        </el-form-item>
        <template v-if="showMore">
          <el-form-item label="ថ្ងៃមានប្រសិទ្ធភាព">
            <el-date-picker v-model="effectiveDates" type="daterange" value-format="YYYY-MM-DD" format="DD/MM/YYYY" start-placeholder="ពីថ្ងៃ" end-placeholder="ដល់ថ្ងៃ" style="width: 260px" />
          </el-form-item>
          <el-form-item v-if="showRank" label="ស័ក្តិចាស់ → ថ្មី">
            <el-select v-model="q.old_rank_id" clearable filterable placeholder="ចាស់" style="width: 150px">
              <el-option v-for="r in lookups.list('ranks')" :key="r.id" :value="r.id" :label="r.name_kh" />
            </el-select>
            <span class="arrow">→</span>
            <el-select v-model="q.new_rank_id" clearable filterable placeholder="ថ្មី" style="width: 150px">
              <el-option v-for="r in lookups.list('ranks')" :key="r.id" :value="r.id" :label="r.name_kh" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="showPosition" label="តំណែងចាស់ → ថ្មី">
            <el-select v-model="q.old_position_id" clearable filterable placeholder="ចាស់" style="width: 170px">
              <el-option v-for="p in lookups.list('positions')" :key="p.id" :value="p.id" :label="p.name_kh" />
            </el-select>
            <span class="arrow">→</span>
            <el-select v-model="q.new_position_id" clearable filterable placeholder="ថ្មី" style="width: 170px">
              <el-option v-for="p in lookups.list('positions')" :key="p.id" :value="p.id" :label="p.name_kh" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="showUnit" label="អង្គភាពចាស់ → ថ្មី">
            <div class="unit-pair">
              <UnitTreeSelect v-model="q.old_unit_id" placeholder="ចាស់" />
              <span class="arrow">→</span>
              <UnitTreeSelect v-model="q.new_unit_id" placeholder="ថ្មី" />
            </div>
          </el-form-item>
          <el-form-item label="អ្នកដាក់សំណើ">
            <el-select v-model="q.created_by" clearable filterable style="width: 180px">
              <el-option v-for="u in users" :key="u.id" :value="u.id" :label="u.full_name" />
            </el-select>
          </el-form-item>
          <el-form-item label="ថ្ងៃបញ្ចូល">
            <el-date-picker v-model="createdDates" type="daterange" value-format="YYYY-MM-DD" format="DD/MM/YYYY" start-placeholder="ពីថ្ងៃ" end-placeholder="ដល់ថ្ងៃ" style="width: 260px" />
          </el-form-item>
        </template>
        <el-form-item>
          <el-button type="primary" native-type="submit" icon="Search">ស្វែងរក</el-button>
          <el-button icon="RefreshLeft" @click="resetFilters">សម្អាត</el-button>
          <el-button link type="primary" @click="showMore = !showMore">{{ showMore ? 'លាក់ការស្វែងរកលម្អិត' : 'ស្វែងរកលម្អិត' }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="rows" stripe border empty-text="គ្មានទិន្នន័យ" @row-dblclick="showDetail">
        <el-table-column type="index" label="ល.រ" width="60" :index="(i) => num((q.page - 1) * q.size + i + 1)" />
        <el-table-column prop="decision_no" label="លេខសេចក្ដីសម្រេច" width="160" />
        <el-table-column label="ថ្ងៃខែឆ្នាំ" width="120"><template #default="{ row }">{{ fmtDate(row.decision_date) }}</template></el-table-column>
        <el-table-column label="ចូលជាធរមាន" width="120"><template #default="{ row }">{{ fmtDate(row.effective_date) }}</template></el-table-column>
        <el-table-column label="ចំនួនយោធិន" width="110" align="center"><template #default="{ row }">{{ num(row.item_count) }}</template></el-table-column>
        <el-table-column label="ស្ថាប័នកងឯកភាព" min-width="160" show-overflow-tooltip><template #default="{ row }">{{ row.institutions.join(', ') }}</template></el-table-column>
        <el-table-column prop="issued_by" label="ចេញដោយ" min-width="140" />
        <el-table-column prop="created_by_name" label="អ្នកដាក់សំណើ" min-width="130" />
        <el-table-column prop="notes" label="កំណត់សម្គាល់" min-width="160" show-overflow-tooltip />
        <el-table-column label="ស្ថានភាព" width="210">
          <template #default="{ row }">
            <el-tag :type="STATUS_TAG[row.status]" size="small">{{ STATUS_TEXT[row.status] }}</el-tag>
            <el-tag v-if="row.overdue" type="danger" size="small" effect="dark" class="overdue">យឺតយ៉ាវ</el-tag>
            <el-tooltip v-if="row.pending" :content="row.apply_error || `ព័ត៌មានយោធិននឹងផ្លាស់ប្ដូរនៅថ្ងៃ ${fmtDate(row.effective_date)}`" placement="top">
              <el-tag :type="row.apply_error ? 'danger' : 'warning'" size="small" class="overdue">{{ row.apply_error ? 'មិនអាចអនុវត្ត' : 'រង់ចាំថ្ងៃចូលជាធរមាន' }}</el-tag>
            </el-tooltip>
            <el-tooltip v-if="row.anomalies.length" placement="top">
              <template #content><div v-for="a in row.anomalies" :key="a">{{ a }}</div></template>
              <el-tag type="warning" size="small" class="overdue">ខុសប្រក្រតី {{ num(row.anomalies.length) }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="សកម្មភាព" width="300" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" icon="View" @click="showDetail(row)" />
            <el-button link icon="Printer" @click="router.push(`/decisions/${row.id}/print`)" />
            <el-tooltip v-if="auth.can(`${module}.export`)" content="ទាញយកសំណើ (Excel)">
              <el-button link icon="Download" @click="exportDecision(row)" />
            </el-tooltip>
            <el-button v-if="row.actions.includes('edit')" link type="primary" icon="Edit" @click="openEdit(row)" />
            <el-button v-for="a in workflowActions(row)" :key="a" link :type="ACTIONS[a].type" :icon="ACTIONS[a].icon" @click="act(row, a)">{{ ACTIONS[a].label }}</el-button>
            <el-tooltip v-if="canCopy(row)" content="ចម្លងជាសំណើថ្មី">
              <el-button link type="primary" icon="CopyDocument" @click="openCopy(row)" />
            </el-tooltip>
            <el-button v-if="row.actions.includes('delete')" link type="danger" icon="Delete" @click="remove(row)" />
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="q.page" v-model:page-size="q.size" class="pager" background
                     layout="total, prev, pager, next" :total="total" @current-change="load" />
    </el-card>

    <!-- create / edit -->
    <el-dialog v-model="dialog" :title="(form.id ? 'កែប្រែ' : 'បង្កើត') + ' សេចក្ដីសម្រេច ' + TITLES[kind]" width="min(1400px, 96vw)"
               :close-on-click-modal="false" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-row :gutter="14">
          <el-col :span="6"><el-form-item label="លេខសេចក្ដីសម្រេច (បើមាន)" prop="decision_no"><el-input v-model="form.decision_no" placeholder="អាចបញ្ចូលពេលចេញលិខិត" /></el-form-item></el-col>
          <el-col :span="5"><el-form-item label="ថ្ងៃខែឆ្នាំ" prop="decision_date"><el-date-picker v-model="form.decision_date" value-format="YYYY-MM-DD" format="DD/MM/YYYY" style="width: 100%" /></el-form-item></el-col>
          <el-col :span="5"><el-form-item label="ចូលជាធរមានពីថ្ងៃ" prop="effective_date"><el-date-picker v-model="form.effective_date" value-format="YYYY-MM-DD" format="DD/MM/YYYY" style="width: 100%" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="ចេញដោយ"><el-input v-model="form.issued_by" /></el-form-item></el-col>
          <el-col :span="24"><el-form-item label="ឯកសារចូល (សំណើ) ដែលពាក់ព័ន្ធ">
            <DocumentSelect v-model="form.incoming_document_id" :initial-label="form.incoming_label" />
          </el-form-item></el-col>
        </el-row>
        <template v-if="warnings.length || warnedCount || errorCount">
          <div class="section-title">ព័ត៌មានខុសប្រក្រតី</div>
          <el-alert v-for="w in warnings" :key="w" :title="w" type="warning" show-icon :closable="false" style="margin-bottom: 6px" />
          <el-alert v-if="errorCount" type="error" show-icon :closable="false" style="margin-bottom: 6px"
                    :title="`យោធិន ${num(errorCount)} នាក់ មិនអាចរក្សាទុកបាន (ក្របខណ្ឌ ឋានន្តរស័ក្តិ ...) — មើលពណ៌ក្រហមនៅជាប់អង្គភាពថ្មី`" />
          <el-alert v-if="warnedCount" type="warning" show-icon :closable="false" style="margin-bottom: 6px"
                    :title="`យោធិន ${num(warnedCount)} នាក់ មានព័ត៌មានខុសប្រក្រតី — មើលនៅជួរឈរ «ព័ត៌មានខុសប្រក្រតី» ជាប់អង្គភាពថ្មី`" />
        </template>
        <el-table :data="form.items" border size="small" :row-class-name="warnRow">
          <el-table-column label="យោធិន" min-width="260">
            <template #default="{ row }">
              <SoldierSelect v-model="row.soldier_id" :initial-label="row.label" @select="(s) => (row.soldier = s)" />
            </template>
          </el-table-column>
          <el-table-column label="បច្ចុប្បន្ន" min-width="200">
            <template #default="{ row }">
              <div v-if="row.soldier" class="small">
                <div>{{ row.soldier.rank_name }}</div>
                <div class="muted">{{ row.soldier.position_name }} · {{ row.soldier.unit_name }}</div>
                <div v-if="row.soldier.institution_name" class="muted">{{ row.soldier.institution_name }}</div>
              </div>
            </template>
          </el-table-column>
          <el-table-column v-if="showRank" :label="kind === 'promote' ? 'ឋានន្តរស័ក្តិថ្មី' : 'ឋានន្តរស័ក្តិថ្មី (បើមាន)'" width="190">
            <template #default="{ row }">
              <el-select v-model="row.new_rank_id" filterable :clearable="kind !== 'promote'">
                <el-option v-for="r in rankOptions(row)" :key="r.id" :value="r.id" :label="r.name_kh" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column v-if="showPosition" label="មុខតំណែងថ្មី (ទំនេរ/ក្របខណ្ឌ)" width="230">
            <template #default="{ row }">
              <el-select v-model="row.new_position_id" filterable clearable popper-class="slot-popper">
                <el-option v-for="p in positionOptions(row)" :key="p.id" :value="p.id" :label="p.name_kh">
                  <span>{{ p.name_kh }}</span>
                  <span v-if="p.slot" class="slot" :class="{ full: p.slot.vacant <= 0 }">ទំនេរ {{ num(Math.max(p.slot.vacant, 0)) }}/{{ num(p.slot.quota) }}</span>
                  <span v-else-if="p.outside" class="slot full">ក្រៅក្របខណ្ឌ</span>
                </el-option>
              </el-select>
            </template>
          </el-table-column>
          <el-table-column v-if="showUnit" label="ស្ថាប័នកងឯកភាពថ្មី" width="190">
            <template #default="{ row }">
              <el-select :model-value="row.new_institution_id" clearable filterable @update:model-value="(v) => setInstitution(row, v ?? null)">
                <el-option v-for="u in institutions" :key="u.id" :value="u.id" :label="u.name_kh" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column v-if="showUnit" label="អង្គភាពថ្មី" width="220">
            <template #default="{ row }"><UnitTreeSelect :model-value="row.new_unit_id" :root-id="row.new_institution_id" @update:model-value="(v) => setUnit(row, v)" /></template>
          </el-table-column>
          <!-- per soldier, next to the new unit (checked on the server while typing) -->
          <el-table-column label="ព័ត៌មានខុសប្រក្រតី" min-width="240">
            <template #default="{ row }">
              <ul v-if="itemErrors[row.soldier_id]?.length || itemWarnings[row.soldier_id]?.length" class="anomalies">
                <li v-for="e in itemErrors[row.soldier_id]" :key="`e-${e}`" class="error"><el-icon><CircleCloseFilled /></el-icon> {{ e }}</li>
                <li v-for="w in itemWarnings[row.soldier_id]" :key="`w-${w}`"><el-icon><WarningFilled /></el-icon> {{ w }}</li>
              </ul>
              <span v-else-if="row.soldier_id" class="ok"><el-icon><CircleCheckFilled /></el-icon> គ្មាន</span>
            </template>
          </el-table-column>
          <el-table-column label="កំណត់សម្គាល់" width="150"><template #default="{ row }"><el-input v-model="row.note" /></template></el-table-column>
          <el-table-column width="50"><template #default="{ $index }"><el-button link type="danger" icon="Delete" @click="form.items.splice($index, 1)" /></template></el-table-column>
        </el-table>
        <el-button icon="Plus" size="small" style="margin-top: 8px" @click="form.items.push(emptyItem())">បន្ថែមយោធិន</el-button>
        <el-form-item label="កំណត់សម្គាល់" style="margin-top: 12px"><el-input v-model="form.notes" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button v-if="auth.can(`${module}.export`)" icon="Download" :loading="downloading" class="footer-left" @click="exportForm">ទាញយក Excel</el-button>
        <el-button @click="dialog = false">បិទ</el-button>
        <el-button type="primary" :loading="saving" @click="save">រក្សាទុកជាសេចក្ដីព្រាង</el-button>
      </template>
    </el-dialog>

    <!-- detail -->
    <el-drawer :model-value="!!detail" size="70%" :title="detail ? `សេចក្ដីសម្រេចលេខ ${detail.decision_no}` : ''" @close="detail = null">
      <template v-if="detail">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="ប្រភេទ">{{ detail.kind_name }}</el-descriptions-item>
          <el-descriptions-item label="ថ្ងៃខែឆ្នាំ">{{ fmtDate(detail.decision_date) }}</el-descriptions-item>
          <el-descriptions-item label="ចូលជាធរមាន">{{ fmtDate(detail.effective_date) }}</el-descriptions-item>
          <el-descriptions-item label="ស្ថានភាព"><el-tag :type="STATUS_TAG[detail.status]">{{ STATUS_TEXT[detail.status] }}</el-tag>
            <el-tag v-if="detail.overdue" type="danger" effect="dark" class="overdue">យឺតយ៉ាវ</el-tag>
            <el-tag v-if="detail.pending" type="warning" class="overdue">រង់ចាំថ្ងៃចូលជាធរមាន</el-tag></el-descriptions-item>
          <el-descriptions-item label="ចេញដោយ" :span="2">{{ detail.issued_by }}</el-descriptions-item>
          <el-descriptions-item label="ឯកសារចូល (សំណើ)">{{ detail.incoming_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="ឯកសារចេញ" :span="2">{{ detail.outgoing_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="កំណត់សម្គាល់" :span="3">{{ detail.notes }}</el-descriptions-item>
        </el-descriptions>
        <el-steps :active="stepIndex(detail.status)" :process-status="['rejected', 'cancelled'].includes(detail.status) ? 'error' : 'process'"
                  finish-status="success" align-center class="wf-steps">
          <el-step v-for="w in WORKFLOW" :key="w.status" :title="w.step" />
        </el-steps>
        <el-alert v-if="detail.pending" :type="detail.apply_error ? 'error' : 'info'" show-icon :closable="false" style="margin-top: 14px"
                  :title="detail.apply_error
                    ? `មិនអាចធ្វើបច្ចុប្បន្នភាពយោធិននៅថ្ងៃចូលជាធរមានបានទេ៖ ${detail.apply_error}`
                    : `បានអនុម័តហើយ — ព័ត៌មានយោធិននឹងត្រូវធ្វើបច្ចុប្បន្នភាពនៅថ្ងៃចូលជាធរមាន ${fmtDate(detail.effective_date)}`" />
        <template v-if="detail.general_anomalies?.length || detailWarned">
          <div class="section-title">ព័ត៌មានខុសប្រក្រតី</div>
          <el-alert v-for="a in detail.general_anomalies" :key="a" :title="a" type="warning" show-icon :closable="false" style="margin-bottom: 6px" />
          <el-alert v-if="detailWarned" type="warning" show-icon :closable="false" style="margin-bottom: 6px"
                    :title="`យោធិន ${num(detailWarned)} នាក់ មានព័ត៌មានខុសប្រក្រតី — មើលនៅជួរឈរជាប់អង្គភាពថ្មី`" />
        </template>
        <!-- a value that does not change is shown as it is (no empty cell); a change as old → new -->
        <el-table :data="detail.items" border size="small" style="margin-top: 14px"
                  :row-class-name="({ row }) => (row.anomalies?.length ? 'warn-row' : '')">
          <el-table-column type="index" label="ល.រ" width="55" />
          <el-table-column prop="military_id" label="អត្តលេខ" width="100" />
          <el-table-column prop="name_kh" label="គោត្តនាមនិងនាម" min-width="140" />
          <el-table-column label="ឋានន្តរស័ក្តិ" min-width="190"><template #default="{ row }">
            <span v-if="row.new_rank_id">{{ row.old_rank || '-' }} → <b>{{ row.new_rank }}</b></span>
            <span v-else>{{ row.old_rank || '-' }}</span>
          </template></el-table-column>
          <el-table-column label="មុខតំណែង" min-width="190"><template #default="{ row }">
            <span v-if="row.new_position_id">{{ row.old_position || '-' }} → <b>{{ row.new_position }}</b></span>
            <span v-else>{{ row.old_position || '-' }}</span>
          </template></el-table-column>
          <el-table-column label="ស្ថាប័នកងឯកភាព" min-width="170"><template #default="{ row }">
            <span v-if="row.new_unit_id && row.new_institution !== row.old_institution">{{ row.old_institution || '-' }} → <b>{{ row.new_institution }}</b></span>
            <span v-else>{{ row.old_institution || '-' }}</span>
          </template></el-table-column>
          <el-table-column :label="detail.kind === 'promote' ? 'អង្គភាព' : 'អង្គភាព (ចាស់ → ថ្មី)'" min-width="200"><template #default="{ row }">
            <span v-if="row.new_unit_id">{{ row.old_unit || '-' }} → <b>{{ row.new_unit }}</b></span>
            <span v-else>{{ row.old_unit || '-' }}</span>
          </template></el-table-column>
          <!-- per soldier, next to the new unit; checked only while the decision can still change something -->
          <el-table-column v-if="anomaliesChecked(detail)" label="ព័ត៌មានខុសប្រក្រតី" min-width="240"><template #default="{ row }">
            <ul v-if="row.anomalies?.length" class="anomalies">
              <li v-for="a in row.anomalies" :key="a"><el-icon><WarningFilled /></el-icon> {{ a }}</li>
            </ul>
            <span v-else class="ok"><el-icon><CircleCheckFilled /></el-icon> គ្មាន</span>
          </template></el-table-column>
          <el-table-column prop="note" label="កំណត់សម្គាល់" min-width="120" />
        </el-table>
        <div class="section-title">កំណត់ត្រាអនុម័ត</div>
        <el-timeline v-if="detail.steps?.length">
          <el-timeline-item v-for="st in detail.steps" :key="st.id" :timestamp="fmtDateTime(st.created_at)" :type="STEP_TYPE[st.action]">
            <b>{{ STEP_ACTION[st.action] }}</b> — {{ st.user_name || 'ប្រព័ន្ធ' }}
            <span class="muted small">({{ st.from_name }} → {{ st.to_name }})</span>
            <div v-if="st.comment" class="comment">{{ st.comment }}</div>
          </el-timeline-item>
        </el-timeline>
        <p v-else class="muted">មិនទាន់មាន</p>
        <div class="section-title">ឯកសារភ្ជាប់</div>
        <FileAttachments owner-type="decision" :owner-id="detail.id" :editable="auth.can(`${module}.update`)" />
        <div class="drawer-actions">
          <el-button icon="Printer" @click="router.push(`/decisions/${detail.id}/print`)">បោះពុម្ព</el-button>
          <el-button v-if="auth.can(`${module}.export`)" icon="Download" :loading="downloading" @click="exportDecision(detail)">ទាញយកសំណើ (Excel)</el-button>
          <el-button v-for="a in workflowActions(detail)" :key="a" :type="ACTIONS[a].type" :icon="ACTIONS[a].icon" @click="act(detail, a)">{{ ACTIONS[a].label }}</el-button>
          <el-button v-if="canCopy(detail)" icon="CopyDocument" @click="openCopy(detail)">ចម្លងជាសំណើថ្មី</el-button>
        </div>
      </template>
    </el-drawer>

    <!-- final approval by the director -->
    <el-dialog :model-value="!!publishing" title="នាយកអនុម័ត" width="520px" @close="publishing = null">
      <template v-if="publishing">
        <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px"
                  :title="publishing.row.effective_date > todayISO()
                    ? `ការអនុម័តនេះជាការសម្រេចចុងក្រោយ៖ ប្រព័ន្ធនឹងចុះលេខលិខិតចេញឥឡូវ ហើយធ្វើបច្ចុប្បន្នភាពប្រវត្តិរូបយោធិននៅថ្ងៃចូលជាធរមាន ${fmtDate(publishing.row.effective_date)}។`
                    : 'ការអនុម័តនេះជាការសម្រេចចុងក្រោយ៖ ប្រព័ន្ធនឹងចុះលេខលិខិតចេញ ហើយធ្វើបច្ចុប្បន្នភាពប្រវត្តិរូបយោធិនទាំងអស់។'" />
        <el-alert v-if="publishing.row.anomalies?.length" type="warning" show-icon :closable="false" style="margin-bottom: 12px"
                  :title="`មានព័ត៌មានខុសប្រក្រតី ${num(publishing.row.anomalies.length)}`">
          <ul class="anomalies"><li v-for="a in publishing.row.anomalies" :key="a">{{ a }}</li></ul>
        </el-alert>
        <el-form label-position="top">
          <el-form-item label="លេខសេចក្ដីសម្រេច (ទុកទំនេរ = តាមលេខលិខិតចេញ)"><el-input v-model="publishing.decision_no" /></el-form-item>
          <el-form-item label="ថ្ងៃចុះហត្ថលេខា"><el-date-picker v-model="publishing.decision_date" value-format="YYYY-MM-DD" format="DD/MM/YYYY" style="width: 100%" /></el-form-item>
          <el-form-item label="មតិ (ស្រេចចិត្ត)"><el-input v-model="publishing.comment" type="textarea" :rows="2" /></el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="publishing = null">បោះបង់</el-button>
        <el-button type="success" icon="Select" :loading="saving" @click="publish">អនុម័ត</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.small { font-size: 12px; line-height: 1.6; }
.drawer-actions { margin-top: 18px; display: flex; gap: 8px; flex-wrap: wrap; }
.overdue { margin-left: 4px; }
.arrow { margin: 0 6px; color: var(--el-text-color-secondary); }
.unit-pair { display: flex; align-items: center; width: 460px; max-width: 100%; }
.unit-pair > :not(.arrow) { flex: 1; min-width: 0; }
.wf-steps { margin-top: 16px; }
.comment { margin-top: 4px; padding: 6px 10px; background: var(--el-fill-color-light); border-radius: 4px; white-space: pre-line; }
/* ព័ត៌មានខុសប្រក្រតី of one soldier, in the column next to the new unit */
.anomalies { margin: 0; padding: 0; list-style: none; font-size: 12px; line-height: 1.6; color: var(--el-color-warning-dark-2); }
.anomalies li { display: flex; gap: 4px; align-items: flex-start; }
.anomalies .el-icon { margin-top: 3px; flex: none; }
.ok { font-size: 12px; color: var(--el-color-success); display: inline-flex; gap: 4px; align-items: center; }
:deep(.warn-row) > td.el-table__cell { background: var(--el-color-warning-light-9) !important; }
/* what saving would refuse, above the warnings of the same soldier */
.anomalies li.error { color: var(--el-color-danger); font-weight: 600; }
:deep(.error-row) > td.el-table__cell { background: var(--el-color-danger-light-9) !important; }
/* vacancies of the staffing table next to each position (the dropdown is teleported: not scoped) */
:global(.slot-popper .slot) { float: right; margin-left: 12px; font-size: 12px; color: var(--el-color-success); }
:global(.slot-popper .slot.full) { color: var(--el-color-danger); }
/* the Excel button sits on the left of the dialog footer, away from save / close */
.footer-left { float: left; }
</style>
