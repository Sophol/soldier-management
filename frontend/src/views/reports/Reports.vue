<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http, { download } from '@/api/http'
import { useAuth } from '@/stores/auth'
import UnitTreeSelect from '@/components/UnitTreeSelect.vue'
import { fmtDate, num } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const auth = useAuth()
const catalog = ref([])
const report = ref(null)
const loading = ref(false)
const year = new Date().getFullYear()
const f = reactive({
  key: route.query.key || 'strength_by_unit', date_from: `${year}-01-01`, date_to: new Date().toISOString().slice(0, 10),
  unit_id: null, kind: null,
})

const usesDates = computed(() => ['movements', 'decisions', 'training', 'discipline', 'awards', 'retirement', 'separation'].includes(f.key))
const kindOptions = computed(() => ({
  decisions: [{ value: 'appoint', label: 'តែងតាំង' }, { value: 'transfer', label: 'ផ្លាស់ប្ដូរ' }, { value: 'promote', label: 'ដំឡើងស័ក្តិ' }],
  training: [{ value: 'long', label: 'រយៈពេលវែង' }, { value: 'short', label: 'រយៈពេលខ្លី' }],
})[f.key] || null)

function params() {
  const p = { unit_id: f.unit_id || undefined, kind: f.kind || undefined }
  if (usesDates.value) Object.assign(p, { date_from: f.date_from, date_to: f.date_to })
  return p
}

async function run() {
  loading.value = true
  try {
    report.value = (await http.get(`/reports/${f.key}`, { params: params() })).data
  } finally {
    loading.value = false
  }
}

function exportXlsx() {
  download(`/reports/${f.key}`, { ...params(), format: 'xlsx' }, `${f.key}.xlsx`)
}

function printReport() {
  const q = new URLSearchParams({ key: f.key, ...JSON.parse(JSON.stringify(params())) })
  router.push(`/reports/print?${q}`)
}

function cell(row, key) {
  const v = row[key]
  if (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v)) return fmtDate(v)
  return typeof v === 'number' ? num(v) : v
}

watch(() => f.key, () => { f.kind = null; run() })
onMounted(async () => {
  catalog.value = (await http.get('/reports')).data
  run()
})
</script>

<template>
  <div class="page">
    <div class="page-head"><h2>របាយការណ៍</h2></div>
    <el-card shadow="never" class="filter-card">
      <el-form inline @submit.prevent="run">
        <el-form-item label="របាយការណ៍">
          <el-select v-model="f.key" style="width: 380px">
            <el-option v-for="r in catalog" :key="r.key" :value="r.key" :label="r.title" />
          </el-select>
        </el-form-item>
        <el-form-item label="អង្គភាព"><div style="width: 240px"><UnitTreeSelect v-model="f.unit_id" /></div></el-form-item>
        <el-form-item v-if="kindOptions" label="ប្រភេទ">
          <el-select v-model="f.kind" clearable style="width: 150px">
            <el-option v-for="o in kindOptions" :key="o.value" v-bind="o" />
          </el-select>
        </el-form-item>
        <template v-if="usesDates">
          <el-form-item label="ចាប់ពី"><el-date-picker v-model="f.date_from" value-format="YYYY-MM-DD" format="DD/MM/YYYY" style="width: 150px" /></el-form-item>
          <el-form-item label="ដល់"><el-date-picker v-model="f.date_to" value-format="YYYY-MM-DD" format="DD/MM/YYYY" style="width: 150px" /></el-form-item>
        </template>
        <el-form-item>
          <el-button type="primary" native-type="submit" icon="Search">បង្ហាញ</el-button>
          <el-button v-if="auth.can('reports.print')" icon="Printer" @click="printReport">បោះពុម្ព</el-button>
          <el-button v-if="auth.can('reports.export')" icon="Download" @click="exportXlsx">Excel</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-loading="loading" shadow="never">
      <template v-if="report">
        <h3 class="title">{{ report.title }}</h3>
        <p v-if="usesDates" class="muted center">ចាប់ពី {{ fmtDate(report.date_from) }} ដល់ {{ fmtDate(report.date_to) }}</p>
        <el-table :data="report.rows" border stripe size="small" empty-text="គ្មានទិន្នន័យ" max-height="620">
          <el-table-column v-for="c in report.columns" :key="c.key" :label="c.label" :min-width="c.key === 'no' ? 60 : 120"
                           :fixed="c.key === 'no' ? 'left' : false" show-overflow-tooltip>
            <template #default="{ row }"><span :class="{ bold: row._level === 1 }">{{ cell(row, c.key) }}</span></template>
          </el-table-column>
        </el-table>
        <div v-if="report.totals" class="totals">
          <template v-for="c in report.columns" :key="c.key">
            <span v-if="report.totals[c.key] !== undefined && report.totals[c.key] !== ''">
              <b>{{ c.label }}:</b> {{ cell(report.totals, c.key) }}
            </span>
          </template>
        </div>
      </template>
    </el-card>
  </div>
</template>

<style scoped>
.title { text-align: center; color: var(--brand); margin: 0 0 4px; }
.center { text-align: center; margin: 0 0 12px; }
.totals { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 16px; background: #f6f8f9; padding: 8px 12px; border-radius: 6px; }
.bold { font-weight: 600; }
</style>
