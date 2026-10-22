<script setup>
/** ការងារបញ្ចូលក្របខ័ណ្ឌយោធិនអាជីព: enter soldiers one by one, or import an Excel file (checked first, then saved). */
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import http, { download } from '@/api/http'
import { useAuth } from '@/stores/auth'
import { num } from '@/utils/format'

const router = useRouter()
const auth = useAuth()
const file = ref(null)
const updateExisting = ref(false)
const result = ref(null)
const busy = ref(false)
const show = ref('all')
const ACTION = { create: ['បន្ថែមថ្មី', 'success'], update: ['ធ្វើបច្ចុប្បន្នភាព', 'warning'], error: ['មានកំហុស', 'danger'] }

function pick(f) {
  file.value = f.raw
  result.value = null
  return false
}

async function send(dryRun) {
  const fd = new FormData()
  fd.append('file', file.value)
  fd.append('dry_run', dryRun)
  fd.append('update_existing', updateExisting.value)
  busy.value = true
  try {
    result.value = (await http.post('/soldiers/import', fd)).data
    show.value = result.value.error ? 'error' : 'all'
  } finally {
    busy.value = false
  }
}

async function save() {
  const r = result.value
  await ElMessageBox.confirm(`រក្សាទុកយោធិនថ្មី ${r.create} នាក់ និងធ្វើបច្ចុប្បន្នភាព ${r.update} នាក់? ជួរដែលមានកំហុស ${r.error} នឹងមិនត្រូវបាននាំចូលទេ។`,
    'នាំចូល', { type: 'warning', confirmButtonText: 'នាំចូល', cancelButtonText: 'បោះបង់' })
  await send(false)
  ElMessage.success(`បាននាំចូល៖ ថ្មី ${result.value.create}, បច្ចុប្បន្នភាព ${result.value.update}`)
}

const rows = computed(() => (result.value?.rows || []).filter((r) => show.value === 'all' || r.action === show.value))
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h2>ការងារបញ្ចូលក្របខ័ណ្ឌយោធិនអាជីព</h2>
      <div class="head-actions">
        <el-button icon="Download" @click="download('/soldiers/import/template', {}, 'soldier-import-template.xlsx')">ទាញយកគំរូ Excel</el-button>
        <el-button v-if="auth.can('soldiers.create')" type="primary" icon="Plus" @click="router.push('/soldiers/new')">បញ្ចូលតាមទម្រង់</el-button>
      </div>
    </div>

    <el-card shadow="never">
      <el-steps :active="result ? (result.dry_run ? 2 : 3) : file ? 1 : 0" finish-status="success" simple>
        <el-step title="ជ្រើសរើសឯកសារ Excel" /><el-step title="ពិនិត្យទិន្នន័យ" /><el-step title="នាំចូល" />
      </el-steps>
      <el-upload drag :auto-upload="false" :show-file-list="false" accept=".xlsx" :on-change="pick" class="drop">
        <el-icon :size="40"><UploadFilled /></el-icon>
        <div>{{ file ? file.name : 'អូសឯកសារ .xlsx មកទីនេះ ឬចុចដើម្បីជ្រើសរើស' }}</div>
        <div class="muted small">ជួរចំណងជើងត្រូវដូចគំរូ (យ៉ាងហោចណាស់ "អត្តលេខ")។ ក្រឡាទំនេរ = មិនប្ដូរ។</div>
      </el-upload>
      <div class="actions">
        <el-checkbox v-if="auth.can('soldiers.update')" v-model="updateExisting">ធ្វើបច្ចុប្បន្នភាពយោធិនដែលមានអត្តលេខរួចហើយ</el-checkbox>
        <el-button type="primary" icon="Search" :disabled="!file" :loading="busy" @click="send(true)">ពិនិត្យទិន្នន័យ</el-button>
        <el-button v-if="result?.dry_run" type="success" icon="Upload" :disabled="!(result.create + result.update)" :loading="busy" @click="save">
          នាំចូល ({{ num(result.create + result.update) }})
        </el-button>
      </div>
    </el-card>

    <el-card v-if="result" shadow="never">
      <el-alert v-if="!result.dry_run" type="success" show-icon :closable="false" title="បាននាំចូលរួចរាល់" style="margin-bottom: 10px" />
      <el-alert v-if="result.unknown_columns.length" type="warning" show-icon :closable="false" style="margin-bottom: 10px"
                :title="`ជួរដែលមិនស្គាល់ (មិនត្រូវបាននាំចូល)៖ ${result.unknown_columns.join(', ')}`" />
      <el-radio-group v-model="show" style="margin-bottom: 10px">
        <el-radio-button value="all">ទាំងអស់ {{ num(result.total) }}</el-radio-button>
        <el-radio-button value="create">ថ្មី {{ num(result.create) }}</el-radio-button>
        <el-radio-button value="update">បច្ចុប្បន្នភាព {{ num(result.update) }}</el-radio-button>
        <el-radio-button value="error">កំហុស {{ num(result.error) }}</el-radio-button>
      </el-radio-group>
      <el-table :data="rows" border size="small" max-height="520" empty-text="គ្មាន">
        <el-table-column label="ជួរ" width="70"><template #default="{ row }">{{ num(row.row) }}</template></el-table-column>
        <el-table-column prop="military_id" label="អត្តលេខ" width="130" />
        <el-table-column label="គោត្តនាមនិងនាម" min-width="160">
          <template #default="{ row }">
            <router-link v-if="row.soldier_id && !result.dry_run" :to="`/soldiers/${row.soldier_id}`">{{ row.name_kh }}</router-link>
            <span v-else>{{ row.name_kh }}</span>
          </template>
        </el-table-column>
        <el-table-column label="លទ្ធផល" width="150">
          <template #default="{ row }"><el-tag :type="ACTION[row.action][1]" size="small">{{ ACTION[row.action][0] }}</el-tag></template>
        </el-table-column>
        <el-table-column label="កំហុស" min-width="320">
          <template #default="{ row }"><div v-for="e in row.errors" :key="e" class="err">{{ e }}</div></template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.drop { margin-top: 16px; }
.actions { display: flex; gap: 12px; align-items: center; margin-top: 12px; flex-wrap: wrap; }
.err { color: var(--el-color-danger); font-size: 12px; }
</style>
