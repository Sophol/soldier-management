<script setup>
// ការងារសោធននិវត្តន៍ (New (2).txt §9), three tabs: the soldiers already retired, those who retired voluntarily
// (ស្ម័គ្រចិត្ត), and those close to the retirement age (ជិតដល់អាយុចូលនិវត្តន៍, GET /retirement-due).
// "បន្ថែម" retires one or many soldiers by military ID (អត្តលេខ) with one letter, and can move them all to one
// ស្ថាប័នកងឯកភាព/អង្គភាព (the move shows in the soldier list); soldiers ticked in the near-retirement list open
// in the same dialog. Edits use the usual form.
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http from '@/api/http'
import { useAuth } from '@/stores/auth'
import { useLookups } from '@/stores/lookups'
import CrudPage from '@/components/CrudPage.vue'
import SoldierSelect from '@/components/SoldierSelect.vue'
import UnitTreeSelect from '@/components/UnitTreeSelect.vue'
import { useTableHeight } from '@/composables/useTableHeight'
import { configs } from '@/crud-configs'
import { fmtDate, genderText, num } from '@/utils/format'
import { exportExcel, fetchAll, filterSummary, printList } from '@/utils/listExport'

const auth = useAuth()
const lookups = useLookups()
const route = useRoute()
const router = useRouter()
const tableHeight = useTableHeight()
const config = { ...configs.retirement, title: 'បញ្ជីយោធិនដែលបានដាក់ឲ្យសោធននិវត្តន៍', noCreate: true }
const voluntaryConfig = {
  ...config, title: 'បញ្ជីយោធិនស្ម័គ្រចិត្តចូលនិវត្តន៍', fixedParams: { type: 'voluntary' },
  filters: config.filters.filter((f) => f.key !== 'type'),
}
const optionsOf = (key) => config.fields.find((f) => f.key === key).options
const TYPES = optionsOf('type')
const CASE_STATUS = optionsOf('case_status')
const STATUS = { ok: ['success', 'ត្រឹមត្រូវ'], inactive: ['warning', 'មិនអាច'], not_found: ['danger', 'រកមិនឃើញ'], out_of_scope: ['danger', 'ក្រៅសិទ្ធិ'] }

const TABS = ['records', 'voluntary', 'due']
const tab = ref(TABS.includes(route.query.tab) ? route.query.tab : 'records')
watch(tab, (t) => router.replace({ query: t === 'records' ? {} : { tab: t } }))

const page = ref(null)
const voluntaryPage = ref(null)
const dialog = ref(false)
const ids = ref('')
const picked = ref(null)
const rows = ref([])
const checking = ref(false)
const saving = ref(false)
const form = reactive({})
const ready = computed(() => rows.value.filter((r) => r.status === 'ok'))

function open(type = 'pension') {
  ids.value = ''
  rows.value = []
  Object.assign(form, { type, case_status: 'submitted', effective_date: null, decision_no: null,
    decision_date: null, pension_amount: null, notes: null, unit_id: null })
  dialog.value = true
}

// ---------------- ជិតដល់អាយុចូលនិវត្តន៍ ----------------
const HORIZONS = [{ value: 6, label: 'ក្នុង ៦ ខែ' }, { value: 12, label: 'ក្នុង ១ ឆ្នាំ' }, { value: 24, label: 'ក្នុង ២ ឆ្នាំ' },
  { value: 60, label: 'ក្នុង ៥ ឆ្នាំ' }, { value: 0, label: 'ហួសអាយុហើយ (មិនទាន់ដាក់និវត្តន៍)' }]
const due = reactive({ months: 12, unit_id: null, q: '', page: 1, size: 20 })
const dueRows = ref([])
const dueTotal = ref(0)
const dueLoading = ref(false)
const dueExporting = ref(false)
const selected = ref([])
const dueParams = () => Object.fromEntries(Object.entries({ months: due.months, unit_id: due.unit_id, q: due.q })
  .filter(([, v]) => v !== null && v !== ''))

async function loadDue() {
  dueLoading.value = true
  try {
    const { data } = await http.get('/retirement-due', { params: { ...dueParams(), page: due.page, size: due.size } })
    dueRows.value = data.items
    dueTotal.value = data.total
  } finally {
    dueLoading.value = false
  }
}
function searchDue() { due.page = 1; loadDue() }
watch(tab, (t) => { if (t === 'due' && !dueRows.value.length) loadDue() }, { immediate: true })

const dueTag = (r) => (r.days_left <= 0 ? 'danger' : r.days_left <= 90 ? 'warning' : 'info')
const dueText = (r) => (r.days_left <= 0 ? `ហួស ${num(-r.days_left)} ថ្ងៃ` : `នៅសល់ ${num(r.days_left)} ថ្ងៃ`)
const DUE_COLUMNS = [
  { label: 'អត្តលេខ', text: (r) => r.military_id },
  { label: 'ឋានន្តរស័ក្តិ', text: (r) => r.rank_name },
  { label: 'គោត្តនាមនិងនាម', text: (r) => r.name_kh },
  { label: 'ភេទ', text: (r) => genderText(r.gender) },
  { label: 'មុខតំណែង', text: (r) => r.position_name },
  { label: 'អង្គភាព', text: (r) => r.unit_name },
  { label: 'ថ្ងៃខែឆ្នាំកំណើត', text: (r) => fmtDate(r.date_of_birth) },
  { label: 'អាយុ', text: (r) => r.age },
  { label: 'អាយុនិវត្តន៍', text: (r) => r.retire_age },
  { label: 'ថ្ងៃគ្រប់អាយុនិវត្តន៍', text: (r) => fmtDate(r.retire_date) },
  { label: 'ស្ថានភាព', text: dueText },
]
async function exportDue(kind) {
  dueExporting.value = true
  try {
    const all = await fetchAll('/retirement-due', dueParams())
    const title = 'បញ្ជីយោធិនជិតដល់អាយុចូលនិវត្តន៍'
    if (kind === 'xlsx') await exportExcel('retirement', title, DUE_COLUMNS, all)
    else {
      printList(router, title, filterSummary([['រយៈពេល', HORIZONS.find((h) => h.value === due.months)?.label],
        ['អង្គភាព', lookups.unitMap[due.unit_id]?.name_kh], ['ពាក្យគន្លឹះ', due.q]]), DUE_COLUMNS, all)
    }
  } finally {
    dueExporting.value = false
  }
}
// the ticked soldiers go into the "បន្ថែម" dialog, checked as if their military IDs were pasted
function retireSelected() {
  open('pension')
  check(selected.value.map((r) => r.military_id).join('\n'))
}

// the pasted IDs, added to the soldiers already listed
async function check(text = ids.value) {
  if (!text.trim()) return
  checking.value = true
  try {
    const { data } = await http.post('/retirements/bulk/check', { military_ids: text })
    const seen = new Set(rows.value.map((r) => r.military_id))
    rows.value.push(...data.filter((r) => !seen.has(r.military_id)))
    ids.value = ''
  } finally {
    checking.value = false
  }
}

function addPicked(s) {
  picked.value = null
  if (s) check(s.military_id)
}

async function save() {
  if (!ready.value.length) return ElMessage.warning('សូមបញ្ចូលអត្តលេខយោធិនដែលត្រឹមត្រូវ')
  if (!form.type || !form.effective_date) return ElMessage.warning('សូមបំពេញ ប្រភេទ និងថ្ងៃចូលជាធរមាន')
  saving.value = true
  try {
    const { data } = await http.post('/retirements/bulk', { ...form, soldier_ids: ready.value.map((r) => r.soldier_id) })
    ElMessage.success(`បានរក្សាទុក ${data.created} នាក់`)
    dialog.value = false
    page.value?.load()
    voluntaryPage.value?.load()
    selected.value = []
    if (dueRows.value.length) loadDue() // the retired soldiers leave the near-retirement list
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="retire-page">
    <el-tabs v-model="tab" class="retire-tabs">
      <el-tab-pane label="បានដាក់ឲ្យសោធននិវត្តន៍" name="records" lazy>
        <CrudPage ref="page" :config="config">
          <template #head-actions>
            <el-button v-if="auth.can('retirement.create')" type="primary" icon="Plus" @click="open()">បន្ថែម</el-button>
          </template>
        </CrudPage>
      </el-tab-pane>

      <el-tab-pane label="ស្ម័គ្រចិត្តចូលនិវត្តន៍" name="voluntary" lazy>
        <CrudPage ref="voluntaryPage" :config="voluntaryConfig">
          <template #head-actions>
            <el-button v-if="auth.can('retirement.create')" type="primary" icon="Plus" @click="open('voluntary')">បន្ថែម</el-button>
          </template>
        </CrudPage>
      </el-tab-pane>

      <el-tab-pane label="ជិតដល់អាយុចូលនិវត្តន៍" name="due" lazy>
        <div class="page">
          <div class="page-head">
            <h2>បញ្ជីយោធិនជិតដល់អាយុចូលនិវត្តន៍</h2>
            <div class="head-actions">
              <el-button v-if="auth.can('retirement.create')" type="primary" icon="Plus" :disabled="!selected.length"
                         @click="retireSelected">ដាក់ឲ្យចូលនិវត្តន៍ ({{ num(selected.length) }})</el-button>
              <el-button v-if="auth.can('retirement.export')" icon="Download" :loading="dueExporting" @click="exportDue('xlsx')">នាំចេញ Excel</el-button>
              <el-button v-if="auth.can('retirement.print')" icon="Printer" :loading="dueExporting" @click="exportDue('pdf')">បោះពុម្ព / PDF</el-button>
            </div>
          </div>
          <el-card shadow="never" class="filter-card">
            <el-form inline @submit.prevent="searchDue">
              <el-form-item><el-input v-model="due.q" placeholder="ឈ្មោះ / អត្តលេខ..." clearable prefix-icon="Search" style="width: 220px" /></el-form-item>
              <el-form-item label="គ្រប់អាយុនិវត្តន៍">
                <el-select v-model="due.months" style="width: 240px" @change="searchDue">
                  <el-option v-for="h in HORIZONS" :key="h.value" v-bind="h" />
                </el-select>
              </el-form-item>
              <el-form-item label="អង្គភាព"><div style="width: 240px"><UnitTreeSelect v-model="due.unit_id" /></div></el-form-item>
              <el-form-item><el-button type="primary" native-type="submit" icon="Search">ស្វែងរក</el-button></el-form-item>
            </el-form>
          </el-card>
          <el-card shadow="never">
            <el-table v-loading="dueLoading" :data="dueRows" stripe border empty-text="គ្មានទិន្នន័យ" :max-height="tableHeight"
                      row-key="id" @selection-change="(v) => (selected = v)">
              <el-table-column v-if="auth.can('retirement.create')" type="selection" width="44" reserve-selection />
              <el-table-column type="index" label="ល.រ" width="60" :index="(i) => num((due.page - 1) * due.size + i + 1)" />
              <el-table-column prop="military_id" label="អត្តលេខ" width="100" />
              <el-table-column prop="rank_name" label="ឋានន្តរស័ក្តិ" width="130" show-overflow-tooltip />
              <el-table-column label="គោត្តនាមនិងនាម" min-width="150" show-overflow-tooltip>
                <template #default="{ row }"><router-link :to="`/soldiers/${row.id}`">{{ row.name_kh }}</router-link></template>
              </el-table-column>
              <el-table-column label="ភេទ" width="70"><template #default="{ row }">{{ genderText(row.gender) }}</template></el-table-column>
              <el-table-column prop="unit_name" label="អង្គភាព" min-width="150" show-overflow-tooltip />
              <el-table-column label="ថ្ងៃខែឆ្នាំកំណើត" width="120"><template #default="{ row }">{{ fmtDate(row.date_of_birth) }}</template></el-table-column>
              <el-table-column label="អាយុ" width="70" align="center"><template #default="{ row }">{{ num(row.age) }}</template></el-table-column>
              <el-table-column label="អាយុនិវត្តន៍" width="100" align="center"><template #default="{ row }">{{ num(row.retire_age) }}</template></el-table-column>
              <el-table-column label="ថ្ងៃគ្រប់អាយុនិវត្តន៍" width="140"><template #default="{ row }">{{ fmtDate(row.retire_date) }}</template></el-table-column>
              <el-table-column label="ស្ថានភាព" width="150">
                <template #default="{ row }"><el-tag :type="dueTag(row)" size="small">{{ dueText(row) }}</el-tag></template>
              </el-table-column>
            </el-table>
            <el-pagination v-model:current-page="due.page" v-model:page-size="due.size" class="pager" background
                           layout="total, sizes, prev, pager, next" :total="dueTotal" :page-sizes="[20, 50, 100]"
                           @current-change="loadDue" @size-change="searchDue" />
          </el-card>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>

  <el-dialog v-model="dialog" title="បន្ថែម ការងារសោធននិវត្តន៍ (មួយ ឬច្រើននាក់)" width="900px" top="4vh" :close-on-click-modal="false">
    <el-form label-position="top">
      <el-row :gutter="12">
        <el-col :md="14">
          <el-form-item label="អត្តលេខ (មួយ ឬច្រើន — មួយបន្ទាត់មួយ ឬបំបែកដោយក្បៀស)">
            <el-input v-model="ids" type="textarea" :rows="3" placeholder="000652&#10;088601, 023840" />
          </el-form-item>
        </el-col>
        <el-col :md="10">
          <el-form-item label="ឬស្វែងរកតាមឈ្មោះ">
            <SoldierSelect v-model="picked" @select="addPicked" />
          </el-form-item>
          <el-button type="primary" plain icon="Search" :loading="checking" @click="check()">ពិនិត្យអត្តលេខ</el-button>
        </el-col>
      </el-row>

      <el-table v-if="rows.length" :data="rows" border size="small" max-height="260" class="picked">
        <el-table-column type="index" label="ល.រ" width="55" />
        <el-table-column prop="military_id" label="អត្តលេខ" width="100" />
        <el-table-column prop="rank_name" label="ឋានន្តរស័ក្តិ" width="130" />
        <el-table-column prop="soldier_name" label="គោត្តនាមនិងនាម" min-width="140" />
        <el-table-column prop="unit_name" label="អង្គភាពបច្ចុប្បន្ន" min-width="150" show-overflow-tooltip />
        <el-table-column label="ស្ថានភាព" width="150">
          <template #default="{ row }">
            <el-tooltip :disabled="!row.message" :content="row.message || ''">
              <el-tag :type="STATUS[row.status][0]" size="small">{{ STATUS[row.status][1] }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column width="50" align="center">
          <template #default="{ $index }"><el-button link type="danger" icon="Close" @click="rows.splice($index, 1)" /></template>
        </el-table-column>
      </el-table>
      <p v-if="rows.length" class="muted small">នឹងរក្សាទុក {{ ready.length }} នាក់ ក្នុងចំណោម {{ rows.length }} (តែអ្នកដែល «ត្រឹមត្រូវ»)</p>

      <el-row :gutter="12">
        <el-col :md="12"><el-form-item label="ប្រភេទ" required>
          <el-select v-model="form.type" style="width: 100%"><el-option v-for="o in TYPES" :key="o.value" v-bind="o" /></el-select>
        </el-form-item></el-col>
        <el-col :md="12"><el-form-item label="ថ្ងៃចូលជាធរមាន" required>
          <el-date-picker v-model="form.effective_date" type="date" value-format="YYYY-MM-DD" format="DD/MM/YYYY" style="width: 100%" placeholder="ថ្ងៃ/ខែ/ឆ្នាំ" />
        </el-form-item></el-col>
        <el-col :md="8"><el-form-item label="លេខលិខិត"><el-input v-model="form.decision_no" /></el-form-item></el-col>
        <el-col :md="8"><el-form-item label="ថ្ងៃខែឆ្នាំលិខិត">
          <el-date-picker v-model="form.decision_date" type="date" value-format="YYYY-MM-DD" format="DD/MM/YYYY" style="width: 100%" placeholder="ថ្ងៃ/ខែ/ឆ្នាំ" />
        </el-form-item></el-col>
        <el-col :md="8"><el-form-item label="ប្រាក់សោធន (រៀល)">
          <el-input-number v-model="form.pension_amount" :min="0" :controls="false" style="width: 100%" />
        </el-form-item></el-col>
        <el-col :md="12"><el-form-item label="ស្ថានភាពសំណុំរឿង" required>
          <el-select v-model="form.case_status" style="width: 100%"><el-option v-for="o in CASE_STATUS" :key="o.value" v-bind="o" /></el-select>
        </el-form-item></el-col>
        <el-col :md="12"><el-form-item label="ផ្លាស់ទៅស្ថាប័នកងឯកភាព-អង្គភាព (ជម្រើស — សម្រាប់អ្នកទាំងអស់)">
          <UnitTreeSelect v-model="form.unit_id" placeholder="មិនផ្លាស់ប្ដូរ" />
        </el-form-item></el-col>
        <el-col :span="24"><el-form-item label="កំណត់សម្គាល់"><el-input v-model="form.notes" type="textarea" :rows="2" /></el-form-item></el-col>
      </el-row>
    </el-form>
    <template #footer>
      <el-button @click="dialog = false">បោះបង់</el-button>
      <el-button type="primary" :loading="saving" :disabled="!ready.length" @click="save">រក្សាទុក ({{ ready.length }} នាក់)</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.picked { margin-bottom: 6px; }
.small { font-size: 12px; }
/* each tab holds a full page (title, filters, table): the tab bar lines up with the page padding */
.retire-tabs > :deep(.el-tabs__header) { margin: 0; padding: 12px 20px 0; }
@media (max-width: 768px) { .retire-tabs > :deep(.el-tabs__header) { padding: 8px 0 0; } }
</style>
