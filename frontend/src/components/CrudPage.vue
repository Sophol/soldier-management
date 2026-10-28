<script setup>
/**
 * Config-driven list + dialog form page.
 * config: { title, endpoint, module, columns, fields, filters, defaults, attachments, formWidth, fixedParams,
 *           afterSave, canEdit(row), canDelete(row), auditFilters }
 * auditFilters: the table records who entered it and when, so the list also filters by អ្នកបញ្ចូល and
 * created / last-updated date (the API's shared filters). Every list can save its filter and export it (Excel / PDF).
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import http from '@/api/http'
import { useAuth } from '@/stores/auth'
import { useLookups } from '@/stores/lookups'
import { fmtDate, num } from '@/utils/format'
import { exportExcel, fetchAll, filterSummary, printList } from '@/utils/listExport'
import FormField from './FormField.vue'
import SavedFilters from './SavedFilters.vue'
import FileAttachments from './FileAttachments.vue'
import PendingFiles from './PendingFiles.vue'

const props = defineProps({ config: { type: Object, required: true } })
const emit = defineEmits(['saved'])
const auth = useAuth()
const lookups = useLookups()
const cfg = computed(() => props.config)

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, size: 20, q: '' })
const filters = reactive({})
const AUDIT_KEYS = ['created_by', 'created_from', 'created_to', 'updated_from', 'updated_to']
const filterKeys = () => [...(cfg.value.filters || []).map((f) => f.key), ...(cfg.value.auditFilters ? AUDIT_KEYS : [])]
// filters can come from the URL (e.g. /documents/incoming?document_type_id=3), so other pages can link here
const route = useRoute()
const router = useRouter()
for (const key of filterKeys()) {
  const v = route.query[key]
  if (v != null && v !== '') filters[key] = /^\d+$/.test(v) ? Number(v) : v
}
if (route.query.q) query.q = route.query.q
const showMore = ref(AUDIT_KEYS.some((k) => filters[k] != null))
const users = ref([])
// a date range picker bound to two filter keys (…_from / …_to)
const range = (prefix) => computed({
  get: () => (filters[`${prefix}_from`] || filters[`${prefix}_to`] ? [filters[`${prefix}_from`], filters[`${prefix}_to`]] : null),
  set: (v) => { filters[`${prefix}_from`] = v?.[0] || null; filters[`${prefix}_to`] = v?.[1] || null },
})
const createdRange = range('created')
const updatedRange = range('updated')
const exporting = ref(false)

const dialog = ref(false)
const saving = ref(false)
const form = ref({})
const editingId = ref(null)
const formRef = ref()
const filesFor = ref(null)
const pendingFiles = ref([])

const canCreate = computed(() => auth.can(`${cfg.value.module}.create`))
const canUpdate = computed(() => auth.can(`${cfg.value.module}.update`))
const canDelete = computed(() => auth.can(`${cfg.value.module}.delete`))
const canExport = computed(() => auth.can(`${cfg.value.module}.export`))
const canPrint = computed(() => auth.can(`${cfg.value.module}.print`))

const rules = computed(() => {
  const r = {}
  for (const f of cfg.value.fields) {
    if (f.required) r[f.key] = [{ required: true, message: `សូមបំពេញ ${f.label}`, trigger: ['blur', 'change'] }]
  }
  return r
})

function filterParams() {
  const params = { ...(cfg.value.fixedParams || {}) }
  if (query.q) params.q = query.q
  for (const [k, v] of Object.entries(filters)) if (v !== null && v !== '' && v !== undefined) params[k] = v
  return params
}

async function load() {
  loading.value = true
  try {
    const params = { ...filterParams(), page: query.page, size: query.size }
    const { data } = await http.get(cfg.value.endpoint, { params })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  Object.keys(filters).forEach((k) => { filters[k] = null })
  query.q = ''
  query.page = 1
  load()
}

// saved filters: the keyword and every filter value (not the fixed params, which belong to the page)
const savedKey = computed(() => cfg.value.savedKey || cfg.value.endpoint + (cfg.value.fixedParams ? `?${new URLSearchParams(cfg.value.fixedParams)}` : ''))
function currentFilter() {
  const out = { q: query.q }
  for (const k of filterKeys()) out[k] = filters[k]
  return out
}
function applySaved(params) {
  Object.keys(filters).forEach((k) => { filters[k] = null })
  for (const k of filterKeys()) if (k in params) filters[k] = params[k]
  query.q = params.q || ''
  query.page = 1
  if (AUDIT_KEYS.some((k) => params[k] != null)) showMore.value = true
  load()
}

// export the whole filtered list (all pages) as shown in the table
function filterValueText(f, v) {
  if (f.type === 'unit') return lookups.unitMap[v]?.name_kh
  if (f.type === 'date') return fmtDate(v)
  if (f.type !== 'select') return v
  if (Array.isArray(f.options)) return f.options.find((o) => o.value === v)?.label ?? v
  if (typeof f.options === 'string') return lookups.name(f.options.replace(/^lookup:/, ''), v) || v
  return v
}
function filterText() {
  const parts = [['ពាក្យគន្លឹះ', query.q]]
  for (const f of cfg.value.filters || []) {
    const v = filters[f.key]
    if (v != null && v !== '') parts.push([f.label, filterValueText(f, v)])
  }
  if (filters.created_by) parts.push(['អ្នកបញ្ចូល', users.value.find((u) => u.id === filters.created_by)?.full_name])
  if (filters.created_from || filters.created_to) parts.push(['ថ្ងៃបញ្ចូល', `${fmtDate(filters.created_from)} → ${fmtDate(filters.created_to)}`])
  if (filters.updated_from || filters.updated_to) parts.push(['ថ្ងៃកែចុងក្រោយ', `${fmtDate(filters.updated_from)} → ${fmtDate(filters.updated_to)}`])
  return filterSummary(parts)
}
async function exportAs(kind) {
  exporting.value = true
  try {
    const all = await fetchAll(cfg.value.endpoint, filterParams())
    const columns = cfg.value.columns.map((col) => ({ label: col.label, text: (row) => cell(row, col) }))
    if (kind === 'xlsx') await exportExcel(cfg.value.module, cfg.value.title, columns, all)
    else printList(router, cfg.value.title, filterText(), columns, all)
  } finally {
    exporting.value = false
  }
}

function openCreate() {
  editingId.value = null
  const base = {}
  for (const f of cfg.value.fields) base[f.key] = f.default !== undefined ? structuredClone(f.default) : null
  form.value = { ...base, ...(cfg.value.defaults || {}), ...(cfg.value.fixedParams || {}) }
  pendingFiles.value = []
  dialog.value = true
  formRef.value?.clearValidate()
}

function openEdit(row) {
  editingId.value = row.id
  const data = {}
  for (const f of cfg.value.fields) {
    const v = row[f.key]
    if (v != null) data[f.key] = typeof v === 'object' ? JSON.parse(JSON.stringify(v)) : v
    else data[f.key] = f.default !== undefined ? structuredClone(f.default) : null
  }
  form.value = { ...data, ...(cfg.value.fixedParams || {}) }
  form.value._row = row
  dialog.value = true
}

async function save() {
  await formRef.value.validate()
  saving.value = true
  try {
    const payload = { ...form.value }
    delete payload._row
    for (const f of cfg.value.fields) if (f.type === 'year' && payload[f.key]) payload[f.key] = Number(payload[f.key])
    if (cfg.value.beforeSave) cfg.value.beforeSave(payload, editingId.value)
    const res = editingId.value
      ? await http.put(`${cfg.value.endpoint}/${editingId.value}`, payload)
      : await http.post(cfg.value.endpoint, payload)
    if (!editingId.value && cfg.value.attachments && pendingFiles.value.length) {
      await uploadPending(res.data.id)
    }
    ElMessage.success('បានរក្សាទុកដោយជោគជ័យ')
    dialog.value = false
    if (cfg.value.refreshLookups) lookups.refresh()
    emit('saved', res.data)
    load()
  } finally {
    saving.value = false
  }
}

async function uploadPending(id) {
  let failed = 0
  for (const f of pendingFiles.value) {
    const fd = new FormData()
    fd.append('file', f)
    try { await http.post(`/files/${cfg.value.attachments}/${id}`, fd) } catch { failed++ }
  }
  pendingFiles.value = []
  if (failed) ElMessage.warning(`ឯកសារភ្ជាប់ ${failed} មិនអាចផ្ទុកបាន`)
}

async function remove(row) {
  await ElMessageBox.confirm('តើអ្នកពិតជាចង់លុបទិន្នន័យនេះមែនទេ?', 'បញ្ជាក់', { type: 'warning', confirmButtonText: 'លុប', cancelButtonText: 'បោះបង់' })
  await http.delete(`${cfg.value.endpoint}/${row.id}`)
  ElMessage.success('បានលុបដោយជោគជ័យ')
  if (cfg.value.refreshLookups) lookups.refresh()
  load()
}

function cell(row, col) {
  const v = col.value ? col.value(row, lookups) : row[col.key]
  if (col.type === 'date') return fmtDate(v)
  if (col.type === 'bool') return v ? 'បាទ/ចាស' : 'ទេ'
  if (typeof v === 'number') return num(v)
  return v ?? ''
}

watch(() => JSON.stringify([cfg.value.endpoint, cfg.value.fixedParams]), () => { query.page = 1; resetFilters() })
watch(showMore, async (v) => { if (v && !users.value.length) users.value = await lookups.loadUsers() }, { immediate: true })
onMounted(load)
defineExpose({ load, openCreate, openEdit })
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h2>{{ cfg.title }}</h2>
      <div class="head-actions">
        <slot name="head-actions" />
        <SavedFilters :module="savedKey" :current="currentFilter" @apply="applySaved" />
        <el-button v-if="canExport" icon="Download" :loading="exporting" @click="exportAs('xlsx')">នាំចេញ Excel</el-button>
        <el-button v-if="canPrint" icon="Printer" :loading="exporting" @click="exportAs('pdf')">បោះពុម្ព / PDF</el-button>
        <el-button v-if="canCreate && !cfg.noCreate" type="primary" icon="Plus" @click="openCreate">បន្ថែម</el-button>
      </div>
    </div>

    <el-card shadow="never" class="filter-card">
      <el-form inline @submit.prevent="query.page = 1; load()">
        <el-form-item>
          <el-input v-model="query.q" placeholder="ពាក្យគន្លឹះ..." clearable prefix-icon="Search" style="width: 220px" />
        </el-form-item>
        <el-form-item v-for="f in cfg.filters || []" :key="f.key" :label="f.label">
          <div :style="{ width: f.width || '200px' }">
            <FormField v-model="filters[f.key]" :field="f" />
          </div>
        </el-form-item>
        <template v-if="cfg.auditFilters && showMore">
          <el-form-item label="អ្នកបញ្ចូល">
            <el-select v-model="filters.created_by" clearable filterable style="width: 180px">
              <el-option v-for="u in users" :key="u.id" :value="u.id" :label="u.full_name" />
            </el-select>
          </el-form-item>
          <el-form-item label="ថ្ងៃបញ្ចូល">
            <el-date-picker v-model="createdRange" type="daterange" value-format="YYYY-MM-DD" format="DD/MM/YYYY"
                            start-placeholder="ពីថ្ងៃ" end-placeholder="ដល់ថ្ងៃ" style="width: 260px" />
          </el-form-item>
          <el-form-item label="ថ្ងៃកែចុងក្រោយ">
            <el-date-picker v-model="updatedRange" type="daterange" value-format="YYYY-MM-DD" format="DD/MM/YYYY"
                            start-placeholder="ពីថ្ងៃ" end-placeholder="ដល់ថ្ងៃ" style="width: 260px" />
          </el-form-item>
        </template>
        <el-form-item>
          <el-button type="primary" native-type="submit" icon="Search">ស្វែងរក</el-button>
          <el-button icon="RefreshLeft" @click="resetFilters">សម្អាត</el-button>
          <el-button v-if="cfg.auditFilters" link type="primary" @click="showMore = !showMore">
            {{ showMore ? 'លាក់ការស្វែងរកលម្អិត' : 'អ្នកបញ្ចូល / ថ្ងៃបញ្ចូល' }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="rows" stripe border empty-text="គ្មានទិន្នន័យ">
        <el-table-column type="index" label="ល.រ" width="60" :index="(i) => num((query.page - 1) * query.size + i + 1)" />
        <el-table-column v-for="col in cfg.columns" :key="col.key" :label="col.label" :width="col.width"
                         :min-width="col.minWidth || 120" show-overflow-tooltip>
          <template #default="{ row }">
            <slot :name="`cell-${col.key}`" :row="row">
              <el-tag v-if="col.tag" :type="col.tag(row)" size="small">{{ cell(row, col) }}</el-tag>
              <span v-else>{{ cell(row, col) }}</span>
            </slot>
          </template>
        </el-table-column>
        <el-table-column label="សកម្មភាព" :width="cfg.actionWidth || 150" fixed="right" align="center">
          <template #default="{ row }">
            <slot name="row-actions" :row="row" />
            <el-tooltip v-if="cfg.attachments" content="ឯកសារភ្ជាប់ (ចុចដើម្បីមើល)">
              <el-button link :type="row.file_count ? 'primary' : 'info'" icon="Paperclip" class="clip-btn" @click="filesFor = row">
                <span v-if="row.file_count">{{ num(row.file_count) }}</span>
              </el-button>
            </el-tooltip>
            <el-button v-if="canUpdate && (!cfg.canEdit || cfg.canEdit(row))" link type="primary" icon="Edit" @click="openEdit(row)" />
            <el-button v-if="canDelete && (!cfg.canDelete || cfg.canDelete(row))" link type="danger" icon="Delete" @click="remove(row)" />
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="query.page" v-model:page-size="query.size" class="pager" background
                     layout="total, sizes, prev, pager, next" :total="total" :page-sizes="[20, 50, 100]"
                     @current-change="load" @size-change="load" />
    </el-card>

    <el-dialog v-model="dialog" :title="(editingId ? 'កែប្រែ ' : 'បន្ថែម ') + cfg.title" :width="cfg.formWidth || '640px'"
               destroy-on-close :close-on-click-modal="false">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-row :gutter="16">
          <template v-for="f in cfg.fields" :key="f.key">
            <el-col v-if="!f.showIf || f.showIf(form)" :span="f.span || 24">
              <el-form-item :label="f.label" :prop="f.key">
                <FormField v-model="form[f.key]" :field="f" :row="form._row || {}" />
              </el-form-item>
            </el-col>
          </template>
        </el-row>
        <slot name="form-extra" :form="form" :editing-id="editingId" />
        <template v-if="cfg.attachments">
          <div class="section-title">ឯកសារភ្ជាប់ / រូបភាព</div>
          <FileAttachments v-if="editingId" :owner-type="cfg.attachments" :owner-id="editingId" :editable="canUpdate" @changed="load" />
          <PendingFiles v-else v-model="pendingFiles" />
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">បោះបង់</el-button>
        <el-button type="primary" :loading="saving" @click="save">រក្សាទុក</el-button>
      </template>
    </el-dialog>

    <el-dialog v-if="cfg.attachments" :model-value="!!filesFor" width="820px" destroy-on-close
               :title="`ឯកសារភ្ជាប់ — ${filesFor?.[cfg.attachmentTitle || 'id'] ?? ''}`" @close="filesFor = null">
      <FileAttachments v-if="filesFor" :owner-type="cfg.attachments" :owner-id="filesFor.id" :editable="canUpdate" @changed="load" />
    </el-dialog>
  </div>
</template>

<style scoped>
.clip-btn { font-weight: 700; }
.clip-btn :deep(span) { margin-left: 2px; }
</style>
