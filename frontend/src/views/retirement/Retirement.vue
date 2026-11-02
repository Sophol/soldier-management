<script setup>
// ការងារសោធននិវត្តន៍: "បន្ថែម" retires one or many soldiers by military ID (អត្តលេខ) with one letter, and can
// move them all to one ស្ថាប័នកងឯកភាព/អង្គភាព (the move shows in the soldier list). Edits use the usual form.
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '@/api/http'
import { useAuth } from '@/stores/auth'
import CrudPage from '@/components/CrudPage.vue'
import SoldierSelect from '@/components/SoldierSelect.vue'
import UnitTreeSelect from '@/components/UnitTreeSelect.vue'
import { configs } from '@/crud-configs'

const auth = useAuth()
const config = { ...configs.retirement, noCreate: true }
const optionsOf = (key) => config.fields.find((f) => f.key === key).options
const TYPES = optionsOf('type')
const CASE_STATUS = optionsOf('case_status')
const STATUS = { ok: ['success', 'ត្រឹមត្រូវ'], inactive: ['warning', 'មិនអាច'], not_found: ['danger', 'រកមិនឃើញ'], out_of_scope: ['danger', 'ក្រៅសិទ្ធិ'] }

const page = ref(null)
const dialog = ref(false)
const ids = ref('')
const picked = ref(null)
const rows = ref([])
const checking = ref(false)
const saving = ref(false)
const form = reactive({})
const ready = computed(() => rows.value.filter((r) => r.status === 'ok'))

function open() {
  ids.value = ''
  rows.value = []
  Object.assign(form, { type: 'pension', case_status: 'submitted', effective_date: null, decision_no: null,
    decision_date: null, pension_amount: null, notes: null, unit_id: null })
  dialog.value = true
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
    page.value.load()
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <CrudPage ref="page" :config="config">
    <template #head-actions>
      <el-button v-if="auth.can('retirement.create')" type="primary" icon="Plus" @click="open">បន្ថែម</el-button>
    </template>
  </CrudPage>

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
</style>
