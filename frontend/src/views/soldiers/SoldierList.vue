<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import http, { download } from '@/api/http'
import { useAuth } from '@/stores/auth'
import { useLookups } from '@/stores/lookups'
import UnitTreeSelect from '@/components/UnitTreeSelect.vue'
import { fmtDate, genderText, num } from '@/utils/format'

const auth = useAuth()
const lookups = useLookups()
const router = useRouter()
const route = useRoute()

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const showAdvanced = ref(false)
const blank = {
  q: '', rank_class_id: null, rank_id: null, unit_id: null, position_id: null, status_id: null, gender: null,
  age_min: null, age_max: null, enlist_year: null, specialty_id: null, education_level_id: null, birth_province_id: null,
}
const f = reactive({ ...blank })
const paging = reactive({ page: 1, size: 20, sort: 'rank', order: 'desc' })
const provinces = ref([])

for (const [k, v] of Object.entries(route.query)) if (k in f) f[k] = /^\d+$/.test(v) ? Number(v) : v
if (Object.keys(route.query).some((k) => k !== 'q' && k in f)) showAdvanced.value = true

const ranks = computed(() => lookups.list('ranks').filter((r) => !f.rank_class_id || r.rank_class_id === f.rank_class_id))

function params() {
  const p = { ...paging }
  for (const [k, v] of Object.entries(f)) if (v !== null && v !== '') p[k] = v
  return p
}

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

function search() { paging.page = 1; load() }
function reset() { Object.assign(f, blank); search() }

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
        <el-button v-if="auth.can('soldiers.export')" icon="Download" @click="exportXlsx">នាំចេញ Excel</el-button>
        <el-button v-if="auth.can('soldiers.create')" type="primary" icon="Plus" @click="router.push('/soldiers/new')">បញ្ចូលយោធិនថ្មី</el-button>
      </div>
    </div>

    <el-card shadow="never" class="filter-card">
      <el-form label-position="top" @submit.prevent="search">
        <el-row :gutter="12">
          <el-col :xs="24" :md="8"><el-form-item label="ស្វែងរក">
            <el-input v-model="f.q" placeholder="ឈ្មោះ / ឈ្មោះឡាតាំង / អត្តលេខ / អត្តសញ្ញាណប័ណ្ណ / ទូរសព្ទ" clearable prefix-icon="Search" />
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
        <el-row v-show="showAdvanced" :gutter="12">
          <el-col :xs="12" :md="4"><el-form-item label="មុខតំណែង">
            <el-select v-model="f.position_id" clearable filterable>
              <el-option v-for="p in lookups.list('positions')" :key="p.id" :value="p.id" :label="p.name_kh" />
            </el-select>
          </el-form-item></el-col>
          <el-col :xs="12" :md="4"><el-form-item label="ស្ថានភាព">
            <el-select v-model="f.status_id" clearable>
              <el-option v-for="s in lookups.list('soldier_status')" :key="s.id" :value="s.id" :label="s.name_kh" />
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
          <el-col :xs="12" :md="4"><el-form-item label="ឆ្នាំចូលបម្រើទ័ព">
            <el-input-number v-model="f.enlist_year" :min="1950" :max="2100" controls-position="right" style="width: 100%" />
          </el-form-item></el-col>
          <el-col :xs="12" :md="4"><el-form-item label="ទីកន្លែងកំណើត (ខេត្ត)">
            <el-select v-model="f.birth_province_id" clearable filterable>
              <el-option v-for="p in provinces" :key="p.id" :value="p.id" :label="p.name_kh" />
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
        </el-row>
        <el-form-item>
          <el-button type="primary" native-type="submit" icon="Search">ស្វែងរក</el-button>
          <el-button icon="RefreshLeft" @click="reset">សម្អាត</el-button>
          <el-button link type="primary" @click="showAdvanced = !showAdvanced">
            {{ showAdvanced ? 'លាក់ការស្វែងរកលម្អិត' : 'ស្វែងរកលម្អិត' }}
          </el-button>
        </el-form-item>
      </el-form>
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
        <el-table-column prop="position_name" label="មុខតំណែង" min-width="130" show-overflow-tooltip />
        <el-table-column prop="unit_name" label="អង្គភាព" min-width="150" show-overflow-tooltip />
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
.range .el-input-number { flex: 1; width: auto; }
.small { font-size: 12px; }
.el-select { width: 100%; }
</style>
