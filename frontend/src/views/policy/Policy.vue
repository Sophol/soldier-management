<script setup>
/**
 * ការងារគោលនយោបាយ (New (2).txt §10): national ID expiry (near / expired), base (ជួលមូលដ្ឋាន, province → village),
 * polling place (ទីបោះឆ្នោត), housing status, family status and dependants. Same filters as the soldier list
 * (GET /soldiers/policy); the filter is kept in the URL and can be opened in the soldier list.
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '@/api/http'
import { useAuth } from '@/stores/auth'
import { useLookups } from '@/stores/lookups'
import UnitTreeSelect from '@/components/UnitTreeSelect.vue'
import { useTableHeight } from '@/composables/useTableHeight'
import { fmtDate, genderText, num } from '@/utils/format'
import { exportExcel, fetchAll, filterSummary, printList } from '@/utils/listExport'

const auth = useAuth()
const lookups = useLookups()
const route = useRoute()
const router = useRouter()
const tableHeight = useTableHeight()

const ID_EXPIRY = [{ value: 'soon', label: 'ជិតផុតកំណត់' }, { value: 'expired', label: 'ផុតកំណត់ហើយ' }, { value: 'missing', label: 'មិនទាន់បញ្ចូលថ្ងៃផុតកំណត់' }]
const HOUSING = [{ value: 'own', label: 'ផ្ទះផ្ទាល់' }, { value: 'rent', label: 'ជួល' }, { value: 'stay', label: 'ស្នាក់' }]
const STATE_TAG = { expired: 'danger', soon: 'warning', missing: 'info', valid: 'success' }

const blank = {
  q: '', unit_id: null, id_expiry: null, housing_status: null, marital_status_id: null, dependents_min: null,
  base_province_id: null, base_district_id: null, voting_province_id: null, voting_district_id: null,
}
const f = reactive({ ...blank })
for (const [k, v] of Object.entries(route.query)) {
  if (k in f && v != null && v !== '') f[k] = /^\d+$/.test(v) && k !== 'q' ? Number(v) : v
}
const paging = reactive({ page: 1, size: 20 })
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const exporting = ref(false)
const provinces = ref([])
const districts = reactive({ base: [], voting: [] })

function filterValues() {
  return Object.fromEntries(Object.entries(f).filter(([, v]) => v !== null && v !== ''))
}

async function load() {
  loading.value = true
  try {
    const { data } = await http.get('/soldiers/policy', { params: { ...filterValues(), page: paging.page, size: paging.size } })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}
function search() {
  paging.page = 1
  router.replace({ query: filterValues() })
  load()
}
function reset() { Object.assign(f, blank); search() }
function quick(state) { f.id_expiry = f.id_expiry === state ? null : state; search() }

async function loadDistricts(which) {
  const pid = f[`${which}_province_id`]
  districts[which] = pid ? (await http.get('/geo/districts', { params: { province_id: pid, size: 100 } })).data.items : []
  if (!districts[which].some((d) => d.id === f[`${which}_district_id`])) f[`${which}_district_id`] = null
}
watch(() => f.base_province_id, () => loadDistricts('base'), { immediate: true })
watch(() => f.voting_province_id, () => loadDistricts('voting'), { immediate: true })

const COLUMNS = [
  { label: 'អត្តលេខ', text: (r) => r.military_id },
  { label: 'ឋានន្តរស័ក្តិ', text: (r) => r.rank_name },
  { label: 'គោត្តនាមនិងនាម', text: (r) => r.name_kh },
  { label: 'ភេទ', text: (r) => genderText(r.gender) },
  { label: 'អង្គភាព', text: (r) => r.unit_name },
  { label: 'លេខអត្តសញ្ញាណប័ណ្ណ', text: (r) => r.national_id },
  { label: 'ថ្ងៃផុតកំណត់', text: (r) => fmtDate(r.national_id_expiry) },
  { label: 'ស្ថានភាពអត្តសញ្ញាណប័ណ្ណ', text: (r) => r.id_expiry_state_name },
  { label: 'ស្ថានភាពគ្រួសារ', text: (r) => r.marital_status_name },
  { label: 'អ្នកក្នុងបន្ទុក', text: (r) => r.dependents_count },
  { label: 'ស្ថានភាពលំនៅ', text: (r) => r.housing_status_name },
  { label: 'ជួលមូលដ្ឋាន', text: (r) => r.base_text },
  { label: 'ទីបោះឆ្នោត', text: (r) => [r.voting_place, r.voting_text].filter(Boolean).join(' — ') },
  { label: 'ទូរស័ព្ទ', text: (r) => r.phone },
]
const name = (list, id) => list.find((x) => x.id === id)?.name_kh
const summary = computed(() => filterSummary([
  ['ពាក្យគន្លឹះ', f.q], ['អង្គភាព', lookups.unitMap[f.unit_id]?.name_kh],
  ['អត្តសញ្ញាណប័ណ្ណ', ID_EXPIRY.find((o) => o.value === f.id_expiry)?.label],
  ['លំនៅ', HOUSING.find((o) => o.value === f.housing_status)?.label],
  ['ស្ថានភាពគ្រួសារ', lookups.name('marital_status', f.marital_status_id)],
  ['អ្នកក្នុងបន្ទុក', f.dependents_min != null ? `≥ ${num(f.dependents_min)}` : null],
  ['ជួលមូលដ្ឋាន', [name(provinces.value, f.base_province_id), name(districts.base, f.base_district_id)].filter(Boolean).join(' › ')],
  ['ទីបោះឆ្នោត', [name(provinces.value, f.voting_province_id), name(districts.voting, f.voting_district_id)].filter(Boolean).join(' › ')],
]))
async function exportAs(kind) {
  exporting.value = true
  try {
    const all = await fetchAll('/soldiers/policy', filterValues())
    if (kind === 'xlsx') await exportExcel('soldiers', 'ការងារគោលនយោបាយ', COLUMNS, all)
    else printList(router, 'ការងារគោលនយោបាយ', summary.value, COLUMNS, all)
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
      <h2>ការងារគោលនយោបាយ</h2>
      <div class="head-actions">
        <el-button icon="User" @click="router.push({ path: '/soldiers', query: filterValues() })">បើកក្នុងបញ្ជីយោធិន</el-button>
        <el-button v-if="auth.can('soldiers.export')" icon="Download" :loading="exporting" @click="exportAs('xlsx')">នាំចេញ Excel</el-button>
        <el-button v-if="auth.can('soldiers.print')" icon="Printer" :loading="exporting" @click="exportAs('pdf')">បោះពុម្ព / PDF</el-button>
      </div>
    </div>

    <el-card shadow="never" class="filter-card">
      <el-form label-position="top" @submit.prevent="search">
        <el-row :gutter="12">
          <el-col :xs="24" :md="6"><el-form-item label="ស្វែងរក">
            <el-input v-model="f.q" placeholder="ឈ្មោះ / អត្តលេខ / អត្តសញ្ញាណប័ណ្ណ / ទូរសព្ទ" clearable prefix-icon="Search" />
          </el-form-item></el-col>
          <el-col :xs="24" :md="6"><el-form-item label="ស្ថាប័នកងឯកភាព-អង្គភាព"><UnitTreeSelect v-model="f.unit_id" /></el-form-item></el-col>
          <el-col :xs="12" :md="4"><el-form-item label="ថ្ងៃផុតកំណត់អត្តសញ្ញាណប័ណ្ណ">
            <el-select v-model="f.id_expiry" clearable><el-option v-for="o in ID_EXPIRY" :key="o.value" v-bind="o" /></el-select>
          </el-form-item></el-col>
          <el-col :xs="12" :md="4"><el-form-item label="ស្ថានភាពលំនៅ">
            <el-select v-model="f.housing_status" clearable><el-option v-for="o in HOUSING" :key="o.value" v-bind="o" /></el-select>
          </el-form-item></el-col>
          <el-col :xs="12" :md="4"><el-form-item label="ស្ថានភាពគ្រួសារ">
            <el-select v-model="f.marital_status_id" clearable>
              <el-option v-for="s in lookups.list('marital_status')" :key="s.id" :value="s.id" :label="s.name_kh" />
            </el-select>
          </el-form-item></el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :xs="12" :md="4"><el-form-item label="អ្នកក្នុងបន្ទុកយ៉ាងតិច">
            <el-input-number v-model="f.dependents_min" :min="0" :max="50" controls-position="right" style="width: 100%" />
          </el-form-item></el-col>
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
        <el-form-item>
          <el-button type="primary" native-type="submit" icon="Search">ស្វែងរក</el-button>
          <el-button icon="RefreshLeft" @click="reset">សម្អាត</el-button>
          <el-divider direction="vertical" />
          <span class="muted">អត្តសញ្ញាណប័ណ្ណសញ្ជាតិ៖</span>
          <el-check-tag v-for="o in ID_EXPIRY.slice(0, 2)" :key="o.value" :checked="f.id_expiry === o.value" class="quick"
                        @change="quick(o.value)">{{ o.label }}</el-check-tag>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="rows" stripe border empty-text="គ្មានទិន្នន័យ" :max-height="tableHeight">
        <el-table-column type="index" label="ល.រ" width="60" fixed="left" :index="(i) => num((paging.page - 1) * paging.size + i + 1)" />
        <el-table-column prop="military_id" label="អត្តលេខ" width="100" fixed="left" />
        <el-table-column prop="rank_name" label="ឋានន្តរស័ក្តិ" width="130" show-overflow-tooltip />
        <el-table-column label="គោត្តនាមនិងនាម" min-width="150" show-overflow-tooltip>
          <template #default="{ row }"><router-link :to="`/soldiers/${row.id}`">{{ row.name_kh }}</router-link></template>
        </el-table-column>
        <el-table-column prop="unit_name" label="អង្គភាព" min-width="140" show-overflow-tooltip />
        <el-table-column prop="national_id" label="លេខអត្តសញ្ញាណប័ណ្ណ" width="140" />
        <el-table-column label="ថ្ងៃផុតកំណត់" width="150">
          <template #default="{ row }">
            <el-tag :type="STATE_TAG[row.id_expiry_state]" size="small">
              {{ row.national_id_expiry ? fmtDate(row.national_id_expiry) : row.id_expiry_state_name }}
            </el-tag>
            <div v-if="row.id_expiry_state === 'soon'" class="muted small">នៅសល់ {{ num(row.id_days_left) }} ថ្ងៃ</div>
          </template>
        </el-table-column>
        <el-table-column prop="marital_status_name" label="ស្ថានភាពគ្រួសារ" width="120" />
        <el-table-column label="អ្នកក្នុងបន្ទុក" width="100" align="center">
          <template #default="{ row }">{{ num(row.dependents_count) }}</template>
        </el-table-column>
        <el-table-column prop="housing_status_name" label="ស្ថានភាពលំនៅ" width="110" />
        <el-table-column prop="base_text" label="ជួលមូលដ្ឋាន" min-width="200" show-overflow-tooltip />
        <el-table-column label="ទីបោះឆ្នោត" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ [row.voting_place, row.voting_text].filter(Boolean).join(' — ') }}</template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="paging.page" v-model:page-size="paging.size" class="pager" background
                     layout="total, sizes, prev, pager, next" :total="total" :page-sizes="[20, 50, 100]"
                     @current-change="load" @size-change="search" />
    </el-card>
  </div>
</template>

<style scoped>
.quick { margin-left: 6px; }
.small { font-size: 12px; }
</style>
