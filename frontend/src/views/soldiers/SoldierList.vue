<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import http, { download } from '@/api/http'
import { useAuth } from '@/stores/auth'
import { useLookups } from '@/stores/lookups'
import SavedFilters from '@/components/SavedFilters.vue'
import UnitTreeSelect from '@/components/UnitTreeSelect.vue'
import { fmtDate, genderText, num } from '@/utils/format'
import { fetchAll, filterSummary, printList } from '@/utils/listExport'

const auth = useAuth()
const lookups = useLookups()
const router = useRouter()
const route = useRoute()

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const exporting = ref(false)
const showAdvanced = ref(false)
const tab = ref('service')
const blank = {
  q: '', rank_class_id: null, rank_id: null, branch: null, unit_id: null, position_id: null, status_id: null, gender: null,
  age_min: null, age_max: null, enlist_year: null, specialty_id: null, education_level_id: null, section_id: null,
  birth_province_id: null, birth_district_id: null, current_province_id: null, current_district_id: null,
  blood_type_id: null, marital_status_id: null, language_id: null, phone: '', military_ids: '',
  nationality: '', ethnicity: '', id_expiry: null, housing_status: null, dependents_min: null,
  base_province_id: null, base_district_id: null, voting_province_id: null, voting_district_id: null,
  dob_from: null, dob_to: null, enlist_from: null, enlist_to: null, rank_date_from: null, rank_date_to: null,
  position_date_from: null, position_date_to: null, service_min: null, service_max: null, in_rank_min: null,
  in_position_min: null, missing: [], has_attachments: null, retire_within: null, promotion_due: false, serving: false,
  created_by: null, created_from: null, created_to: null, updated_from: null, updated_to: null,
}
const f = reactive(structuredClone(blank))
const paging = reactive({ page: 1, size: 20, sort: 'rank', order: 'desc' })
const provinces = ref([])
const districts = reactive({ birth: [], current: [], base: [], voting: [] })
const users = ref([])

const MISSING = [
  { value: 'photo', label: 'ខ្វះរូបថត' }, { value: 'dob', label: 'ខ្វះថ្ងៃខែឆ្នាំកំណើត' },
  { value: 'enlistment', label: 'ខ្វះថ្ងៃខែឆ្នាំចូលទ័ព' }, { value: 'rank_date', label: 'ខ្វះថ្ងៃខែឆ្នាំឡើងស័ក្តិ' },
  { value: 'national_id', label: 'ខ្វះលេខអត្តសញ្ញាណប័ណ្ណ' }, { value: 'unit', label: 'មិនទាន់មានអង្គភាព' },
  { value: 'phone', label: 'ខ្វះលេខទូរស័ព្ទ' }, { value: 'attachments', label: 'ខ្វះឯកសារភ្ជាប់' },
]
const BRANCHES = [{ value: 'army', label: 'ស័ក្តិជើងគោក' }, { value: 'navy', label: 'ស័ក្តិកងទ័ពជើងទឹក' }]
const RETIRE = [1, 2, 5]
const HOUSING = [{ value: 'own', label: 'ផ្ទះផ្ទាល់' }, { value: 'rent', label: 'ជួល' }, { value: 'stay', label: 'ស្នាក់' }]
const ID_EXPIRY = [{ value: 'soon', label: 'ជិតផុតកំណត់' }, { value: 'expired', label: 'ផុតកំណត់ហើយ' }, { value: 'missing', label: 'មិនទាន់បញ្ចូលថ្ងៃផុតកំណត់' }]

/** URL query / saved filter -> filter values */
function assign(values) {
  Object.assign(f, structuredClone(blank))
  for (const [k, v] of Object.entries(values)) {
    if (!(k in f) || v == null || v === '') continue
    if (k === 'missing') f.missing = Array.isArray(v) ? v : String(v).split(',')
    else if (k === 'promotion_due' || k === 'serving') f[k] = v === true || v === 'true'
    else f[k] = typeof v === 'string' && /^\d+$/.test(v) && !['q', 'phone', 'military_ids', 'nationality', 'ethnicity'].includes(k) ? Number(v) : v
  }
}
const BASIC = ['q', 'rank_class_id', 'rank_id', 'unit_id']
assign(route.query)
if (Object.keys(route.query).some((k) => !BASIC.includes(k) && k in f)) showAdvanced.value = true

const ranks = computed(() => lookups.list('ranks').filter((r) => (!f.rank_class_id || r.rank_class_id === f.rank_class_id)
  && (!f.branch || [f.branch, 'all'].includes(r.branch))))

// a date range picker bound to two filter keys
const range = (from, to) => computed({
  get: () => (f[from] || f[to] ? [f[from], f[to]] : null),
  set: (v) => { f[from] = v?.[0] || null; f[to] = v?.[1] || null },
})
const dobRange = range('dob_from', 'dob_to')
const enlistRange = range('enlist_from', 'enlist_to')
const rankDateRange = range('rank_date_from', 'rank_date_to')
const positionDateRange = range('position_date_from', 'position_date_to')
const createdRange = range('created_from', 'created_to')
const updatedRange = range('updated_from', 'updated_to')

/** the filter in use, without empty values (also what a saved filter keeps) */
function filterValues() {
  const p = {}
  for (const [k, v] of Object.entries(f)) {
    if (v === null || v === '' || v === false || (Array.isArray(v) && !v.length)) continue
    p[k] = Array.isArray(v) ? v.join(',') : v
  }
  return p
}
const params = () => ({ ...paging, ...filterValues() })

async function load() {
  loading.value = true
  try {
    const { data } = await http.get('/soldiers', { params: params() })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

// the URL follows the filter, so a filtered list can be bookmarked, shared or opened from the dashboard
function search() {
  paging.page = 1
  router.replace({ query: filterValues() })
  load()
}
function reset() { Object.assign(f, structuredClone(blank)); search() }
function applySaved(values) {
  assign(values)
  if (Object.keys(values).some((k) => !BASIC.includes(k))) showAdvanced.value = true
  search()
}

// cascading province -> district (ទីកន្លែងកំណើត / ទីលំនៅបច្ចុប្បន្ន)
async function loadDistricts(which) {
  const pid = f[`${which}_province_id`]
  districts[which] = pid ? (await http.get('/geo/districts', { params: { province_id: pid, size: 100 } })).data.items : []
  // a district of another province no longer applies (a saved filter sets both at once and keeps its district)
  if (!districts[which].some((d) => d.id === f[`${which}_district_id`])) f[`${which}_district_id`] = null
}
watch(() => f.birth_province_id, () => loadDistricts('birth'), { immediate: true })
watch(() => f.current_province_id, () => loadDistricts('current'), { immediate: true })
watch(() => f.base_province_id, () => loadDistricts('base'), { immediate: true })
watch(() => f.voting_province_id, () => loadDistricts('voting'), { immediate: true })
watch(() => f.branch, () => { if (f.rank_id && !ranks.value.some((r) => r.id === f.rank_id)) f.rank_id = null })
watch(showAdvanced, async (v) => { if (v && !users.value.length) users.value = await lookups.loadUsers() }, { immediate: true })

// active filters as removable tags
const name = (list, id) => list.find((x) => x.id === id)?.name_kh
const span = (a, b, fmt = (x) => x) => `${a != null && a !== '' ? fmt(a) : '…'} → ${b != null && b !== '' ? fmt(b) : '…'}`
const chips = computed(() => {
  const out = []
  const add = (keys, label, text) => out.push({ keys, label, text })
  if (f.q) add(['q'], 'ពាក្យគន្លឹះ', f.q)
  if (f.rank_class_id) add(['rank_class_id'], 'ថ្នាក់', lookups.name('rank_classes', f.rank_class_id))
  if (f.branch) add(['branch'], 'ប្រភេទស័ក្តិ', BRANCHES.find((b) => b.value === f.branch)?.label)
  if (f.rank_id) add(['rank_id'], 'ឋានន្តរស័ក្តិ', lookups.name('ranks', f.rank_id))
  if (f.unit_id) add(['unit_id'], 'អង្គភាព', lookups.unitMap[f.unit_id]?.name_kh)
  if (f.position_id) add(['position_id'], 'មុខតំណែង', lookups.name('positions', f.position_id))
  if (f.status_id) add(['status_id'], 'ស្ថានភាព', lookups.name('soldier_status', f.status_id))
  if (f.serving) add(['serving'], 'ស្ថានភាព', 'កំពុងបម្រើការ (គ្រប់ស្ថានភាពសកម្ម)')
  if (f.gender) add(['gender'], 'ភេទ', genderText(f.gender))
  if (f.age_min != null || f.age_max != null) add(['age_min', 'age_max'], 'អាយុ', span(f.age_min, f.age_max, num))
  if (f.service_min != null || f.service_max != null) add(['service_min', 'service_max'], 'ឆ្នាំសេវា', span(f.service_min, f.service_max, num))
  if (f.in_rank_min != null) add(['in_rank_min'], 'កាន់ស័ក្តិ', `≥ ${num(f.in_rank_min)} ឆ្នាំ`)
  if (f.in_position_min != null) add(['in_position_min'], 'កាន់មុខតំណែង', `≥ ${num(f.in_position_min)} ឆ្នាំ`)
  for (const [from, to, label] of [['dob_from', 'dob_to', 'ថ្ងៃកំណើត'], ['enlist_from', 'enlist_to', 'ថ្ងៃចូលទ័ព'],
    ['rank_date_from', 'rank_date_to', 'ថ្ងៃឡើងស័ក្តិ'], ['position_date_from', 'position_date_to', 'ថ្ងៃមុខតំណែង'],
    ['created_from', 'created_to', 'ថ្ងៃបញ្ចូល'], ['updated_from', 'updated_to', 'ថ្ងៃកែចុងក្រោយ']]) {
    if (f[from] || f[to]) add([from, to], label, span(f[from], f[to], fmtDate))
  }
  if (f.enlist_year) add(['enlist_year'], 'ឆ្នាំចូលទ័ព', num(f.enlist_year))
  if (f.retire_within) add(['retire_within'], 'ជិតនិវត្ត', `ក្នុង ${num(f.retire_within)} ឆ្នាំ`)
  if (f.promotion_due) add(['promotion_due'], 'គ្រប់ឆ្នាំឡើងស័ក្តិ', 'បាទ')
  for (const m of f.missing) add([`missing:${m}`], 'ទិន្នន័យខ្វះ', MISSING.find((x) => x.value === m)?.label)
  if (f.has_attachments) add(['has_attachments'], 'ឯកសារភ្ជាប់', f.has_attachments === 'yes' ? 'មាន' : 'ខ្វះ')
  if (f.section_id) add(['section_id'], 'ផ្នែក', lookups.name('specialty_section', f.section_id))
  if (f.specialty_id) add(['specialty_id'], 'ជំនាញ', lookups.name('specialties', f.specialty_id))
  if (f.education_level_id) add(['education_level_id'], 'កម្រិតវប្បធម៌', lookups.name('education_level', f.education_level_id))
  if (f.language_id) add(['language_id'], 'ភាសា', lookups.name('language', f.language_id))
  if (f.blood_type_id) add(['blood_type_id'], 'ឈាម', lookups.name('blood_type', f.blood_type_id))
  if (f.marital_status_id) add(['marital_status_id'], 'ស្ថានភាពគ្រួសារ', lookups.name('marital_status', f.marital_status_id))
  if (f.phone) add(['phone'], 'ទូរស័ព្ទ', f.phone)
  if (f.birth_province_id) add(['birth_province_id', 'birth_district_id'], 'កំណើត', [name(provinces.value, f.birth_province_id), name(districts.birth, f.birth_district_id)].filter(Boolean).join(' › '))
  if (f.current_province_id) add(['current_province_id', 'current_district_id'], 'លំនៅ', [name(provinces.value, f.current_province_id), name(districts.current, f.current_district_id)].filter(Boolean).join(' › '))
  if (f.nationality) add(['nationality'], 'សញ្ជាតិ', f.nationality)
  if (f.ethnicity) add(['ethnicity'], 'ជនជាតិ', f.ethnicity)
  if (f.id_expiry) add(['id_expiry'], 'អត្តសញ្ញាណប័ណ្ណ', ID_EXPIRY.find((x) => x.value === f.id_expiry)?.label)
  if (f.housing_status) add(['housing_status'], 'លំនៅ', HOUSING.find((x) => x.value === f.housing_status)?.label)
  if (f.dependents_min != null) add(['dependents_min'], 'អ្នកក្នុងបន្ទុក', `≥ ${num(f.dependents_min)}`)
  if (f.base_province_id) add(['base_province_id', 'base_district_id'], 'ជួលមូលដ្ឋាន', [name(provinces.value, f.base_province_id), name(districts.base, f.base_district_id)].filter(Boolean).join(' › '))
  if (f.voting_province_id) add(['voting_province_id', 'voting_district_id'], 'ទីបោះឆ្នោត', [name(provinces.value, f.voting_province_id), name(districts.voting, f.voting_district_id)].filter(Boolean).join(' › '))
  if (f.military_ids) add(['military_ids'], 'បញ្ជីអត្តលេខ', `${num(f.military_ids.split(/[\s,;]+/).filter(Boolean).length)} អត្តលេខ`)
  if (f.created_by) add(['created_by'], 'អ្នកបញ្ចូល', users.value.find((u) => u.id === f.created_by)?.full_name)
  return out
})
function removeChip(c) {
  for (const k of c.keys) {
    if (k.startsWith('missing:')) f.missing = f.missing.filter((m) => m !== k.slice(8))
    else f[k] = structuredClone(blank[k])
  }
  search()
}

function onSort({ prop, order }) {
  const map = { name_kh: 'name', military_id: 'military_id', rank_name: 'rank', enlistment_date: 'enlistment_date', age: 'date_of_birth' }
  paging.sort = map[prop] || 'rank'
  paging.order = order === 'ascending' ? 'asc' : 'desc'
  if (prop === 'age') paging.order = order === 'ascending' ? 'desc' : 'asc'
  load()
}

async function remove(row) {
  await ElMessageBox.confirm(`លុបយោធិន "${row.name_kh}"?`, 'បញ្ជាក់', { type: 'warning' })
  await http.delete(`/soldiers/${row.id}`)
  ElMessage.success('បានលុប')
  load()
}

function exportXlsx() {
  const p = params()
  delete p.page
  delete p.size
  download('/soldiers/export', p, 'soldiers.xlsx')
}

// PDF: the printable list of every soldier matching the filter
const PRINT_COLUMNS = [
  { label: 'អត្តលេខ', text: (r) => r.military_id },
  { label: 'ឋានន្តរស័ក្តិ', text: (r) => r.rank_name },
  { label: 'គោត្តនាមនិងនាម', text: (r) => r.name_kh },
  { label: 'ឈ្មោះឡាតាំង', text: (r) => r.name_latin },
  { label: 'ភេទ', text: (r) => genderText(r.gender) },
  { label: 'ថ្ងៃខែឆ្នាំកំណើត', text: (r) => fmtDate(r.date_of_birth) },
  { label: 'មុខតំណែង', text: (r) => r.position_name },
  { label: 'អង្គភាព', text: (r) => r.unit_name },
  { label: 'ចូលបម្រើទ័ព', text: (r) => fmtDate(r.enlistment_date) },
  { label: 'ឡើងស័ក្តិ', text: (r) => fmtDate(r.rank_date) },
  { label: 'ស្ថានភាព', text: (r) => r.status_name },
]
async function exportPdf() {
  exporting.value = true
  try {
    const p = params()
    delete p.page
    delete p.size
    const all = await fetchAll('/soldiers', p)
    printList(router, 'បញ្ជីយោធិន', filterSummary(chips.value.map((c) => [c.label, c.text])), PRINT_COLUMNS, all)
  } finally {
    exporting.value = false
  }
}

onMounted(async () => {
  load()
  provinces.value = (await http.get('/geo/provinces', { params: { size: 100 } })).data.items
})
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h2>បញ្ជីយោធិន</h2>
      <div class="head-actions">
        <SavedFilters module="soldiers" :current="filterValues" @apply="applySaved" />
        <el-button v-if="auth.can('soldiers.export')" icon="Download" @click="exportXlsx">នាំចេញ Excel</el-button>
        <el-button v-if="auth.can('soldiers.print')" icon="Printer" :loading="exporting" @click="exportPdf">បោះពុម្ព / PDF</el-button>
        <el-button v-if="auth.can('soldiers.create')" type="primary" icon="Plus" @click="router.push('/soldiers/new')">បញ្ចូលយោធិនថ្មី</el-button>
      </div>
    </div>

    <el-card shadow="never" class="filter-card">
      <el-form label-position="top" @submit.prevent="search">
        <el-row :gutter="12">
          <el-col :xs="24" :md="8"><el-form-item label="ស្វែងរក">
            <el-input v-model="f.q" placeholder="ឈ្មោះ ខ្មែរ/ឡាតាំង / អត្តលេខ / អត្តសញ្ញាណប័ណ្ណ / ទូរសព្ទ" clearable prefix-icon="Search" />
          </el-form-item></el-col>
          <el-col :xs="12" :md="4"><el-form-item label="ថ្នាក់">
            <el-select v-model="f.rank_class_id" clearable @change="f.rank_id = null">
              <el-option v-for="c in lookups.list('rank_classes')" :key="c.id" :value="c.id" :label="c.name_kh" />
            </el-select>
          </el-form-item></el-col>
          <el-col :xs="12" :md="4"><el-form-item label="ឋានន្តរស័ក្តិ">
            <el-select v-model="f.rank_id" clearable filterable>
              <el-option v-for="r in ranks" :key="r.id" :value="r.id" :label="r.name_kh" />
            </el-select>
          </el-form-item></el-col>
          <el-col :xs="24" :md="8"><el-form-item label="អង្គភាព (រួមទាំងអង្គភាពរង)"><UnitTreeSelect v-model="f.unit_id" /></el-form-item></el-col>
        </el-row>

        <el-tabs v-show="showAdvanced" v-model="tab" class="adv-tabs">
          <el-tab-pane label="សេវា និងស្ថានភាព" name="service">
            <el-row :gutter="12">
              <el-col :xs="12" :md="4"><el-form-item label="ស្ថានភាពសេវា">
                <el-select v-model="f.status_id" clearable>
                  <el-option v-for="s in lookups.list('soldier_status')" :key="s.id" :value="s.id" :label="s.name_kh" />
                </el-select>
              </el-form-item></el-col>
              <el-col :xs="12" :md="4"><el-form-item label="ប្រភេទស័ក្តិ (គោក/ទឹក)">
                <el-select v-model="f.branch" clearable>
                  <el-option v-for="b in BRANCHES" :key="b.value" :value="b.value" :label="b.label" />
                </el-select>
              </el-form-item></el-col>
              <el-col :xs="12" :md="4"><el-form-item label="មុខតំណែង">
                <el-select v-model="f.position_id" clearable filterable>
                  <el-option v-for="p in lookups.list('positions')" :key="p.id" :value="p.id" :label="p.name_kh" />
                </el-select>
              </el-form-item></el-col>
              <el-col :xs="12" :md="3"><el-form-item label="ភេទ">
                <el-select v-model="f.gender" clearable>
                  <el-option value="M" label="ប្រុស" /><el-option value="F" label="ស្រី" />
                </el-select>
              </el-form-item></el-col>
              <el-col :xs="12" :md="5"><el-form-item label="អាយុ (ពី - ដល់)">
                <div class="range">
                  <el-input-number v-model="f.age_min" :min="0" :max="100" controls-position="right" />
                  <span>-</span>
                  <el-input-number v-model="f.age_max" :min="0" :max="100" controls-position="right" />
                </div>
              </el-form-item></el-col>
              <el-col :xs="12" :md="4"><el-form-item label="ឆ្នាំសេវា (ពី - ដល់)">
                <div class="range">
                  <el-input-number v-model="f.service_min" :min="0" :max="60" controls-position="right" />
                  <span>-</span>
                  <el-input-number v-model="f.service_max" :min="0" :max="60" controls-position="right" />
                </div>
              </el-form-item></el-col>
              <el-col :xs="12" :md="4"><el-form-item label="កាន់ស័ក្តិបច្ចុប្បន្នយ៉ាងតិច (ឆ្នាំ)">
                <el-input-number v-model="f.in_rank_min" :min="0" :max="60" controls-position="right" style="width: 100%" />
              </el-form-item></el-col>
              <el-col :xs="12" :md="4"><el-form-item label="កាន់មុខតំណែងយ៉ាងតិច (ឆ្នាំ)">
                <el-input-number v-model="f.in_position_min" :min="0" :max="60" controls-position="right" style="width: 100%" />
              </el-form-item></el-col>
              <el-col :xs="12" :md="4"><el-form-item label="ជិតនិវត្ត">
                <el-select v-model="f.retire_within" clearable>
                  <el-option v-for="y in RETIRE" :key="y" :value="y" :label="`ក្នុង ${num(y)} ឆ្នាំ`" />
                </el-select>
              </el-form-item></el-col>
              <el-col :xs="12" :md="4"><el-form-item label="តែយោធិនកំពុងបម្រើការ">
                <el-switch v-model="f.serving" />
              </el-form-item></el-col>
              <el-col :xs="12" :md="4"><el-form-item label="គ្រប់ឆ្នាំឡើងស័ក្តិ">
                <el-switch v-model="f.promotion_due" />
              </el-form-item></el-col>
              <el-col :xs="12" :md="4"><el-form-item label="ឆ្នាំចូលបម្រើទ័ព">
                <el-input-number v-model="f.enlist_year" :min="1950" :max="2100" controls-position="right" style="width: 100%" />
              </el-form-item></el-col>
            </el-row>
          </el-tab-pane>

          <el-tab-pane label="ជួរកាលបរិច្ឆេទ" name="dates">
            <el-row :gutter="12">
              <el-col :xs="24" :md="8"><el-form-item label="ថ្ងៃខែឆ្នាំកំណើត (ពីថ្ងៃ → ដល់ថ្ងៃ)">
                <el-date-picker v-model="dobRange" type="daterange" value-format="YYYY-MM-DD" format="DD/MM/YYYY" start-placeholder="ពីថ្ងៃ" end-placeholder="ដល់ថ្ងៃ" />
              </el-form-item></el-col>
              <el-col :xs="24" :md="8"><el-form-item label="ថ្ងៃខែឆ្នាំបម្រើចូលទ័ព">
                <el-date-picker v-model="enlistRange" type="daterange" value-format="YYYY-MM-DD" format="DD/MM/YYYY" start-placeholder="ពីថ្ងៃ" end-placeholder="ដល់ថ្ងៃ" />
              </el-form-item></el-col>
              <el-col :xs="24" :md="8"><el-form-item label="ថ្ងៃខែឆ្នាំឡើងស័ក្តិ">
                <el-date-picker v-model="rankDateRange" type="daterange" value-format="YYYY-MM-DD" format="DD/MM/YYYY" start-placeholder="ពីថ្ងៃ" end-placeholder="ដល់ថ្ងៃ" />
              </el-form-item></el-col>
              <el-col :xs="24" :md="8"><el-form-item label="ថ្ងៃខែឆ្នាំមុខតំណែង">
                <el-date-picker v-model="positionDateRange" type="daterange" value-format="YYYY-MM-DD" format="DD/MM/YYYY" start-placeholder="ពីថ្ងៃ" end-placeholder="ដល់ថ្ងៃ" />
              </el-form-item></el-col>
            </el-row>
          </el-tab-pane>

          <el-tab-pane label="ទិន្នន័យខ្វះ" name="missing">
            <el-row :gutter="12">
              <el-col :xs="24" :md="16"><el-form-item label="ទិន្នន័យខ្វះ (ជ្រើសច្រើន = ខ្វះទាំងអស់)">
                <el-checkbox-group v-model="f.missing">
                  <el-checkbox v-for="m in MISSING" :key="m.value" :value="m.value">{{ m.label }}</el-checkbox>
                </el-checkbox-group>
              </el-form-item></el-col>
              <el-col :xs="12" :md="4"><el-form-item label="ស្ថានភាពឯកសារភ្ជាប់">
                <el-select v-model="f.has_attachments" clearable>
                  <el-option value="yes" label="មានឯកសារភ្ជាប់" /><el-option value="no" label="ខ្វះឯកសារភ្ជាប់" />
                </el-select>
              </el-form-item></el-col>
            </el-row>
          </el-tab-pane>

          <el-tab-pane label="ជំនាញ និងព័ត៌មានផ្ទាល់ខ្លួន" name="personal">
            <el-row :gutter="12">
              <el-col :xs="12" :md="4"><el-form-item label="ផ្នែក">
                <el-select v-model="f.section_id" clearable filterable>
                  <el-option v-for="o in lookups.list('specialty_section')" :key="o.id" :value="o.id" :label="o.name_kh" />
                </el-select>
              </el-form-item></el-col>
              <el-col :xs="12" :md="4"><el-form-item label="ជំនាញឯកទេស">
                <el-select v-model="f.specialty_id" clearable filterable>
                  <el-option v-for="s in lookups.list('specialties')" :key="s.id" :value="s.id" :label="s.name_kh" />
                </el-select>
              </el-form-item></el-col>
              <el-col :xs="12" :md="4"><el-form-item label="កម្រិតវប្បធម៌">
                <el-select v-model="f.education_level_id" clearable>
                  <el-option v-for="s in lookups.list('education_level')" :key="s.id" :value="s.id" :label="s.name_kh" />
                </el-select>
              </el-form-item></el-col>
              <el-col :xs="12" :md="4"><el-form-item label="ភាសាបរទេស">
                <el-select v-model="f.language_id" clearable filterable>
                  <el-option v-for="s in lookups.list('language')" :key="s.id" :value="s.id" :label="s.name_kh" />
                </el-select>
              </el-form-item></el-col>
              <el-col :xs="12" :md="4"><el-form-item label="ប្រភេទឈាម">
                <el-select v-model="f.blood_type_id" clearable>
                  <el-option v-for="s in lookups.list('blood_type')" :key="s.id" :value="s.id" :label="s.name_kh" />
                </el-select>
              </el-form-item></el-col>
              <el-col :xs="12" :md="4"><el-form-item label="ស្ថានភាពគ្រួសារ">
                <el-select v-model="f.marital_status_id" clearable>
                  <el-option v-for="s in lookups.list('marital_status')" :key="s.id" :value="s.id" :label="s.name_kh" />
                </el-select>
              </el-form-item></el-col>
              <el-col :xs="12" :md="4"><el-form-item label="លេខទូរស័ព្ទ">
                <el-input v-model="f.phone" clearable />
              </el-form-item></el-col>
              <el-col :xs="12" :md="4"><el-form-item label="សញ្ជាតិ">
                <el-input v-model="f.nationality" clearable />
              </el-form-item></el-col>
              <el-col :xs="12" :md="4"><el-form-item label="ជនជាតិ">
                <el-input v-model="f.ethnicity" clearable />
              </el-form-item></el-col>
              <el-col :xs="12" :md="5"><el-form-item label="ខេត្តកំណើត">
                <el-select v-model="f.birth_province_id" clearable filterable>
                  <el-option v-for="p in provinces" :key="p.id" :value="p.id" :label="p.name_kh" />
                </el-select>
              </el-form-item></el-col>
              <el-col :xs="12" :md="5"><el-form-item label="ស្រុក/ខណ្ឌកំណើត">
                <el-select v-model="f.birth_district_id" clearable filterable :disabled="!f.birth_province_id">
                  <el-option v-for="d in districts.birth" :key="d.id" :value="d.id" :label="d.name_kh" />
                </el-select>
              </el-form-item></el-col>
              <el-col :xs="12" :md="5"><el-form-item label="ខេត្តទីលំនៅ">
                <el-select v-model="f.current_province_id" clearable filterable>
                  <el-option v-for="p in provinces" :key="p.id" :value="p.id" :label="p.name_kh" />
                </el-select>
              </el-form-item></el-col>
              <el-col :xs="12" :md="5"><el-form-item label="ស្រុក/ខណ្ឌទីលំនៅ">
                <el-select v-model="f.current_district_id" clearable filterable :disabled="!f.current_province_id">
                  <el-option v-for="d in districts.current" :key="d.id" :value="d.id" :label="d.name_kh" />
                </el-select>
              </el-form-item></el-col>
            </el-row>
          </el-tab-pane>

          <el-tab-pane label="គោលនយោបាយ" name="policy">
            <el-row :gutter="12">
              <el-col :xs="12" :md="5"><el-form-item label="ថ្ងៃផុតកំណត់អត្តសញ្ញាណប័ណ្ណ">
                <el-select v-model="f.id_expiry" clearable>
                  <el-option v-for="o in ID_EXPIRY" :key="o.value" :value="o.value" :label="o.label" />
                </el-select>
              </el-form-item></el-col>
              <el-col :xs="12" :md="4"><el-form-item label="ស្ថានភាពលំនៅ">
                <el-select v-model="f.housing_status" clearable>
                  <el-option v-for="o in HOUSING" :key="o.value" :value="o.value" :label="o.label" />
                </el-select>
              </el-form-item></el-col>
              <el-col :xs="12" :md="4"><el-form-item label="អ្នកក្នុងបន្ទុកយ៉ាងតិច">
                <el-input-number v-model="f.dependents_min" :min="0" :max="50" controls-position="right" style="width: 100%" />
              </el-form-item></el-col>
              <el-col :xs="12" :md="4"><el-form-item label="ស្ថានភាពគ្រួសារ">
                <el-select v-model="f.marital_status_id" clearable>
                  <el-option v-for="s in lookups.list('marital_status')" :key="s.id" :value="s.id" :label="s.name_kh" />
                </el-select>
              </el-form-item></el-col>
            </el-row>
            <el-row :gutter="12">
              <el-col :xs="12" :md="5"><el-form-item label="ជួលមូលដ្ឋាន (ខេត្ត)">
                <el-select v-model="f.base_province_id" clearable filterable>
                  <el-option v-for="p in provinces" :key="p.id" :value="p.id" :label="p.name_kh" />
                </el-select>
              </el-form-item></el-col>
              <el-col :xs="12" :md="5"><el-form-item label="ជួលមូលដ្ឋាន (ស្រុក/ខណ្ឌ)">
                <el-select v-model="f.base_district_id" clearable filterable :disabled="!f.base_province_id">
                  <el-option v-for="d in districts.base" :key="d.id" :value="d.id" :label="d.name_kh" />
                </el-select>
              </el-form-item></el-col>
              <el-col :xs="12" :md="5"><el-form-item label="ទីបោះឆ្នោត (ខេត្ត)">
                <el-select v-model="f.voting_province_id" clearable filterable>
                  <el-option v-for="p in provinces" :key="p.id" :value="p.id" :label="p.name_kh" />
                </el-select>
              </el-form-item></el-col>
              <el-col :xs="12" :md="5"><el-form-item label="ទីបោះឆ្នោត (ស្រុក/ខណ្ឌ)">
                <el-select v-model="f.voting_district_id" clearable filterable :disabled="!f.voting_province_id">
                  <el-option v-for="d in districts.voting" :key="d.id" :value="d.id" :label="d.name_kh" />
                </el-select>
              </el-form-item></el-col>
            </el-row>
          </el-tab-pane>

          <el-tab-pane label="បញ្ជីអត្តលេខ" name="ids">
            <el-form-item label="វាយ/បិទភ្ជាប់បញ្ជីអត្តលេខ (មួយបន្ទាត់មួយ ឬបំបែកដោយក្បៀស) រួចចុចស្វែងរក ឬនាំចេញ Excel">
              <el-input v-model="f.military_ids" type="textarea" :rows="4" placeholder="199600001&#10;199900002" />
            </el-form-item>
          </el-tab-pane>

          <el-tab-pane label="អ្នកបញ្ចូល" name="audit">
            <el-row :gutter="12">
              <el-col :xs="24" :md="6"><el-form-item label="អ្នកបញ្ចូល (user)">
                <el-select v-model="f.created_by" clearable filterable>
                  <el-option v-for="u in users" :key="u.id" :value="u.id" :label="`${u.full_name} (${u.username})`" />
                </el-select>
              </el-form-item></el-col>
              <el-col :xs="24" :md="8"><el-form-item label="ថ្ងៃបញ្ចូល">
                <el-date-picker v-model="createdRange" type="daterange" value-format="YYYY-MM-DD" format="DD/MM/YYYY" start-placeholder="ពីថ្ងៃ" end-placeholder="ដល់ថ្ងៃ" />
              </el-form-item></el-col>
              <el-col :xs="24" :md="8"><el-form-item label="ថ្ងៃកែចុងក្រោយ">
                <el-date-picker v-model="updatedRange" type="daterange" value-format="YYYY-MM-DD" format="DD/MM/YYYY" start-placeholder="ពីថ្ងៃ" end-placeholder="ដល់ថ្ងៃ" />
              </el-form-item></el-col>
            </el-row>
          </el-tab-pane>
        </el-tabs>

        <el-form-item>
          <el-button type="primary" native-type="submit" icon="Search">ស្វែងរក</el-button>
          <el-button icon="RefreshLeft" @click="reset">សម្អាត</el-button>
          <el-button link type="primary" @click="showAdvanced = !showAdvanced">
            {{ showAdvanced ? 'លាក់ការស្វែងរកលម្អិត' : 'ស្វែងរកលម្អិត' }}
          </el-button>
        </el-form-item>
      </el-form>
      <div v-if="chips.length" class="chips">
        <span class="muted small">Filter កំពុងប្រើ៖</span>
        <el-tag v-for="c in chips" :key="c.keys.join()" closable @close="removeChip(c)">{{ c.label }}: {{ c.text }}</el-tag>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="rows" stripe border empty-text="គ្មានទិន្នន័យ" @sort-change="onSort"
                @row-dblclick="(r) => router.push(`/soldiers/${r.id}`)">
        <el-table-column type="index" label="ល.រ" width="60" :index="(i) => num((paging.page - 1) * paging.size + i + 1)" />
        <el-table-column prop="military_id" label="អត្តលេខ" width="110" sortable="custom" />
        <el-table-column prop="rank_name" label="ឋានន្តរស័ក្តិ" width="130" sortable="custom" />
        <el-table-column prop="name_kh" label="គោត្តនាមនិងនាម" min-width="150" sortable="custom">
          <template #default="{ row }">
            <el-link type="primary" @click="router.push(`/soldiers/${row.id}`)">{{ row.name_kh }}</el-link>
            <div class="muted small">{{ row.name_latin }}</div>
          </template>
        </el-table-column>
        <el-table-column label="ភេទ" width="70"><template #default="{ row }">{{ genderText(row.gender) }}</template></el-table-column>
        <el-table-column prop="age" label="អាយុ" width="80" sortable="custom"><template #default="{ row }">{{ num(row.age) }}</template></el-table-column>
        <el-table-column label="មុខតំណែង" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.position_name }}<div v-if="row.time_in_position" class="muted small">{{ num(row.time_in_position) }}</div></template>
        </el-table-column>
        <el-table-column label="ស្ថាប័នកងឯកភាព-អង្គភាព" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ row.unit_path }}</template>
        </el-table-column>
        <el-table-column prop="enlistment_date" label="ចូលបម្រើទ័ព" width="125" sortable="custom">
          <template #default="{ row }">{{ fmtDate(row.enlistment_date) }}<div class="muted small">{{ num(row.service_length) }}</div></template>
        </el-table-column>
        <el-table-column label="ឡើងស័ក្តិ" width="125">
          <template #default="{ row }">{{ fmtDate(row.rank_date) }}<div class="muted small">{{ num(row.time_in_rank) }}</div></template>
        </el-table-column>
        <el-table-column label="ស្ថានភាព" width="130">
          <template #default="{ row }">
            <el-tag v-if="row.status_name" size="small" :type="['retired', 'category2', 'separated'].includes(row.status_code) ? 'info' : 'success'">{{ row.status_name }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="សកម្មភាព" width="150" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" icon="View" @click="router.push(`/soldiers/${row.id}`)" />
            <el-button v-if="auth.can('soldiers.update')" link type="primary" icon="Edit" @click="router.push(`/soldiers/${row.id}/edit`)" />
            <el-button v-if="auth.can('soldiers.print')" link icon="Printer" @click="router.push(`/soldiers/${row.id}/print`)" />
            <el-button v-if="auth.can('soldiers.delete')" link type="danger" icon="Delete" @click="remove(row)" />
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="paging.page" v-model:page-size="paging.size" class="pager" background
                     layout="total, sizes, prev, pager, next" :total="total" :page-sizes="[20, 50, 100, 200]"
                     @current-change="load" @size-change="load" />
    </el-card>
  </div>
</template>

<style scoped>
.range { display: flex; gap: 6px; align-items: center; width: 100%; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.adv-tabs :deep(.el-date-editor) { width: 100%; }
.range .el-input-number { flex: 1; width: auto; }
.small { font-size: 12px; }
.el-select { width: 100%; }
</style>
