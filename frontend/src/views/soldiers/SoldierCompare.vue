<script setup>
/** ការប្រៀបធៀប: compare an Excel list with the soldier list on the chosen fields (matched by military ID). */
import { computed, onMounted, ref } from 'vue'
import http, { download } from '@/api/http'
import UnitTreeSelect from '@/components/UnitTreeSelect.vue'
import { num } from '@/utils/format'

const file = ref(null)
const fields = ref([])
const catalog = ref([])
const unitId = ref(null)
const result = ref(null)
const busy = ref(false)
const show = ref('different')
const STATUS = {
  same: ['ដូចគ្នា', 'success'], different: ['ខុសគ្នា', 'danger'],
  missing_in_db: ['មិនមានក្នុងប្រព័ន្ធ', 'warning'], missing_in_file: ['មិនមានក្នុងឯកសារ', 'info'],
}

onMounted(async () => {
  catalog.value = (await http.get('/soldiers/import/fields')).data.filter((f) => f.key !== 'military_id')
})

function pick(f) {
  file.value = f.raw
  result.value = null
  return false
}

function form(format) {
  const fd = new FormData()
  fd.append('file', file.value)
  if (fields.value.length) fd.append('fields', fields.value.join(','))
  if (unitId.value) fd.append('unit_id', unitId.value)
  fd.append('format', format)
  return fd
}

async function run() {
  busy.value = true
  try {
    result.value = (await http.post('/soldiers/compare', form('json'))).data
    show.value = result.value.different ? 'different' : 'all'
  } finally {
    busy.value = false
  }
}

async function exportResult() {
  const res = await http.post('/soldiers/compare', form('xlsx'), { responseType: 'blob' })
  const href = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = href
  a.download = 'compare.xlsx'
  a.click()
  setTimeout(() => URL.revokeObjectURL(href), 1000)
}

const rows = computed(() => (result.value?.rows || []).filter((r) => show.value === 'all' || r.status === show.value))
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h2>ការប្រៀបធៀបបញ្ជីយោធិន ជាមួយឯកសារ Excel</h2>
      <div class="head-actions">
        <el-button icon="Download" @click="download('/soldiers/export', {}, 'soldiers.xlsx')">នាំចេញបញ្ជីបច្ចុប្បន្ន</el-button>
      </div>
    </div>

    <el-card shadow="never">
      <el-row :gutter="14">
        <el-col :md="10">
          <el-upload drag :auto-upload="false" :show-file-list="false" accept=".xlsx" :on-change="pick">
            <el-icon :size="36"><UploadFilled /></el-icon>
            <div>{{ file ? file.name : 'ឯកសារ .xlsx ដែលត្រូវប្រៀបធៀប' }}</div>
            <div class="muted small">ត្រូវមានជួរ "អត្តលេខ"។ ប្រើគំរូដូចការនាំចេញ។</div>
          </el-upload>
        </el-col>
        <el-col :md="14">
          <el-form label-position="top">
            <el-form-item label="ព័ត៌មានដែលត្រូវប្រៀបធៀប (ទុកទំនេរ = គ្រប់ជួរក្នុងឯកសារ)">
              <el-select v-model="fields" multiple filterable collapse-tags collapse-tags-tooltip style="width: 100%">
                <el-option v-for="f in catalog" :key="f.key" :value="f.key" :label="f.label" />
              </el-select>
            </el-form-item>
            <el-form-item label="បង្ហាញយោធិនក្នុងអង្គភាពនេះ ដែលមិនមានក្នុងឯកសារ (ស្រេចចិត្ត)">
              <UnitTreeSelect v-model="unitId" />
            </el-form-item>
            <el-button type="primary" icon="Switch" :disabled="!file" :loading="busy" @click="run">ប្រៀបធៀប</el-button>
            <el-button v-if="result" icon="Download" @click="exportResult">នាំចេញលទ្ធផល Excel</el-button>
          </el-form>
        </el-col>
      </el-row>
    </el-card>

    <el-card v-if="result" shadow="never">
      <el-radio-group v-model="show" style="margin-bottom: 10px">
        <el-radio-button value="all">ទាំងអស់ {{ num(result.rows.length) }}</el-radio-button>
        <el-radio-button v-for="(s, k) in STATUS" :key="k" :value="k">{{ s[0] }} {{ num(result[k]) }}</el-radio-button>
      </el-radio-group>
      <el-table :data="rows" border size="small" max-height="560" empty-text="គ្មាន">
        <el-table-column label="ជួរ" width="70"><template #default="{ row }">{{ num(row.row) }}</template></el-table-column>
        <el-table-column prop="military_id" label="អត្តលេខ" width="130" />
        <el-table-column label="គោត្តនាមនិងនាម" min-width="150">
          <template #default="{ row }">
            <router-link v-if="row.soldier_id" :to="`/soldiers/${row.soldier_id}`">{{ row.name_kh }}</router-link>
            <span v-else>{{ row.name_kh }}</span>
          </template>
        </el-table-column>
        <el-table-column label="លទ្ធផល" width="160">
          <template #default="{ row }"><el-tag :type="STATUS[row.status][1]" size="small">{{ STATUS[row.status][0] }}</el-tag></template>
        </el-table-column>
        <el-table-column label="ចំណុចខុសគ្នា (ក្នុងប្រព័ន្ធ → ក្នុងឯកសារ)" min-width="380">
          <template #default="{ row }">
            <div v-for="d in row.diffs" :key="d.field" class="diff">
              <b>{{ d.label }}៖</b> <span class="db">{{ d.db || '∅' }}</span> → <span class="file">{{ d.file || '∅' }}</span>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.diff { font-size: 12px; line-height: 1.8; }
.db { color: var(--el-color-success); }
.file { color: var(--el-color-danger); }
</style>
