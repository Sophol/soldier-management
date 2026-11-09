<script setup>
// ការផ្លាស់ប្ដូរស្ថាប័នកងឯកភាព / ការងារកើនថយ. "បន្ថែម" takes one or many military IDs (អត្តលេខ):
//  - កើន: every soldier entered joins the chosen ស្ថាប័នកងឯកភាព (or a unit inside it) — the soldier's unit changes,
//    with a history row and the movements out of the old unit and into the new one;
//  - ថយ: a movement out of the chosen ស្ថាប័នកងឯកភាព is recorded for each soldier (the profile stays as it is).
// Each soldier is checked on the server as the choices change (errors stop saving; warnings are only shown).
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import http from '@/api/http'
import { useAuth } from '@/stores/auth'
import { useLookups } from '@/stores/lookups'
import CrudPage from '@/components/CrudPage.vue'
import SoldierSelect from '@/components/SoldierSelect.vue'
import UnitTreeSelect from '@/components/UnitTreeSelect.vue'
import { MOVEMENT_REASON_LIST, configs } from '@/crud-configs'
import { num, todayISO } from '@/utils/format'

const auth = useAuth()
const lookups = useLookups()
const config = { ...configs.strength, noCreate: true }
const STATUS = { ok: ['success', 'ត្រឹមត្រូវ'], warning: ['warning', 'ត្រឹមត្រូវ (មានការព្រមាន)'], error: ['danger', 'មិនអាច'], not_found: ['danger', 'រកមិនឃើញ'] }

const page = ref(null)
const dialog = ref(false)
const ids = ref('')
const picked = ref(null)
const rows = ref([])
const checking = ref(false)
const saving = ref(false)
const form = reactive({})
const ready = computed(() => rows.value.filter((r) => ['ok', 'warning'].includes(r.status)))
const institutions = computed(() => lookups.unitTree.filter((u) => u.level === 1))
const institutionOf = (unitId) => Number(lookups.unitMap[unitId]?.path?.split('/')[1]) || null
const reasons = computed(() => MOVEMENT_REASON_LIST.filter((r) => r.dir === form.direction || r.dir === 'both'))
// the unit the soldiers join / leave: the chosen unit, or the ស្ថាប័នកងឯកភាព itself
const target = computed(() => form.unit_id || form.institution_id || null)

function open() {
  ids.value = ''
  rows.value = []
  Object.assign(form, { direction: 'in', reason: 'transfer_in', institution_id: null, unit_id: null, movement_date: todayISO(), note: null })
  dialog.value = true
}

function setInstitution(id) {
  form.institution_id = id ?? null
  if (institutionOf(form.unit_id) !== form.institution_id) form.unit_id = null
}
function setUnit(id) {
  form.unit_id = id ?? null
  if (id) form.institution_id = institutionOf(id)
}
watch(() => form.direction, () => {
  if (!reasons.value.some((r) => r.value === form.reason)) form.reason = reasons.value[0]?.value || null
})

// checks the IDs on the server with the current choices; text = new IDs to add to the list
async function check(text = '') {
  const all = [...rows.value.map((r) => r.military_id), ...text.split(/[\s,;]+/).filter(Boolean)]
  if (!all.length) return
  checking.value = true
  try {
    const { data } = await http.post('/strength-movements/bulk/check', {
      military_ids: all.join('\n'), direction: form.direction, reason: form.reason, unit_id: target.value,
    })
    rows.value = data
    if (text) ids.value = ''
  } finally {
    checking.value = false
  }
}
// the soldiers listed are checked again when what they would do changes
watch(() => [form.direction, form.reason, target.value], () => { if (dialog.value && rows.value.length) check() })

function addPicked(s) {
  picked.value = null
  if (s) check(s.military_id)
}
function removeRow(i) { rows.value.splice(i, 1) }

async function save() {
  if (!target.value || !form.reason || !form.movement_date) return ElMessage.warning('សូមបំពេញ មូលហេតុ ស្ថាប័នកងឯកភាព និងកាលបរិច្ឆេទ')
  if (!ready.value.length) return ElMessage.warning('សូមបញ្ចូលអត្តលេខយោធិនដែលត្រឹមត្រូវ')
  saving.value = true
  try {
    const { data } = await http.post('/strength-movements/bulk', {
      soldier_ids: ready.value.map((r) => r.soldier_id), direction: form.direction, reason: form.reason,
      unit_id: target.value, movement_date: form.movement_date, note: form.note || null,
    })
    ElMessage.success(form.direction === 'in'
      ? `បានផ្លាស់ ${num(data.saved)} នាក់ ទៅ ${lookups.unitMap[target.value]?.name_kh || ''}`
      : `បានកត់ត្រាថយ ${num(data.saved)} នាក់`)
    dialog.value = false
    page.value?.load()
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <CrudPage ref="page" :config="config">
    <template #head-actions>
      <el-button v-if="auth.can('strength.create')" type="primary" icon="Plus" @click="open">បន្ថែម</el-button>
    </template>
  </CrudPage>

  <el-dialog v-model="dialog" title="បន្ថែម ការផ្លាស់ប្ដូរស្ថាប័នកងឯកភាព (មួយ ឬច្រើននាក់)" width="1000px" top="4vh" :close-on-click-modal="false">
    <el-form label-position="top">
      <el-row :gutter="12">
        <el-col :md="6"><el-form-item label="កើន/ថយ" required>
          <el-radio-group v-model="form.direction">
            <el-radio-button value="in">កើន</el-radio-button>
            <el-radio-button value="out">ថយ</el-radio-button>
          </el-radio-group>
        </el-form-item></el-col>
        <el-col :md="9"><el-form-item label="មូលហេតុ" required>
          <el-select v-model="form.reason" style="width: 100%"><el-option v-for="o in reasons" :key="o.value" :value="o.value" :label="o.label" /></el-select>
        </el-form-item></el-col>
        <el-col :md="9"><el-form-item label="កាលបរិច្ឆេទ" required>
          <el-date-picker v-model="form.movement_date" type="date" value-format="YYYY-MM-DD" format="DD/MM/YYYY" style="width: 100%" placeholder="ថ្ងៃ/ខែ/ឆ្នាំ" />
        </el-form-item></el-col>
        <el-col :md="12"><el-form-item :label="form.direction === 'in' ? 'ផ្លាស់ទៅស្ថាប័នកងឯកភាព (សម្រាប់អ្នកទាំងអស់)' : 'ថយចេញពីស្ថាប័នកងឯកភាព'" required>
          <el-select :model-value="form.institution_id" clearable filterable style="width: 100%" @update:model-value="setInstitution">
            <el-option v-for="u in institutions" :key="u.id" :value="u.id" :label="u.name_kh" />
          </el-select>
        </el-form-item></el-col>
        <el-col :md="12"><el-form-item :label="form.direction === 'in' ? 'អង្គភាព (ជម្រើស — ទុកទំនេរ = ស្ថាប័នកងឯកភាព)' : 'អង្គភាព (ជម្រើស)'">
          <UnitTreeSelect :model-value="form.unit_id" :root-id="form.institution_id" @update:model-value="setUnit" />
        </el-form-item></el-col>
      </el-row>
      <el-alert v-if="form.direction === 'out'" type="info" show-icon :closable="false" style="margin-bottom: 10px"
                title="ថយ៖ កត់ត្រាតែការថយប៉ុណ្ណោះ (ប្រវត្តិរូបយោធិនមិនផ្លាស់ប្ដូរ)។ ដើម្បីផ្លាស់យោធិនទៅស្ថាប័នកងឯកភាពផ្សេង សូមជ្រើស «កើន» នៅស្ថាប័នថ្មី — ការថយពីស្ថាប័នចាស់នឹងកត់ត្រាដោយស្វ័យប្រវត្តិ។" />

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
          <el-button type="primary" plain icon="Search" :loading="checking" @click="check(ids)">ពិនិត្យអត្តលេខ</el-button>
        </el-col>
      </el-row>

      <el-table v-if="rows.length" v-loading="checking" :data="rows" border size="small" max-height="300">
        <el-table-column type="index" label="ល.រ" width="55" />
        <el-table-column prop="military_id" label="អត្តលេខ" width="90" />
        <el-table-column prop="rank_name" label="ឋានន្តរស័ក្តិ" width="120" />
        <el-table-column prop="soldier_name" label="គោត្តនាមនិងនាម" min-width="130" />
        <el-table-column label="ស្ថាប័នកងឯកភាព / អង្គភាពបច្ចុប្បន្ន" min-width="190" show-overflow-tooltip>
          <template #default="{ row }">{{ [row.institution_name, row.unit_name].filter(Boolean).join(' › ') }}</template>
        </el-table-column>
        <el-table-column label="ស្ថានភាព" min-width="220">
          <template #default="{ row }">
            <el-tag :type="STATUS[row.status][0]" size="small">{{ STATUS[row.status][1] }}</el-tag>
            <div v-for="e in row.errors" :key="`e-${e}`" class="msg error">{{ e }}</div>
            <div v-for="w in row.warnings" :key="`w-${w}`" class="msg warn">{{ w }}</div>
          </template>
        </el-table-column>
        <el-table-column width="50" align="center">
          <template #default="{ $index }"><el-button link type="danger" icon="Close" @click="removeRow($index)" /></template>
        </el-table-column>
      </el-table>
      <p v-if="rows.length" class="muted small">នឹងរក្សាទុក {{ num(ready.length) }} នាក់ ក្នុងចំណោម {{ num(rows.length) }} (អ្នកដែល «មិនអាច» ឬ «រកមិនឃើញ» មិនត្រូវបានរក្សាទុកទេ)</p>

      <el-form-item label="កំណត់សម្គាល់" style="margin-top: 8px"><el-input v-model="form.note" type="textarea" :rows="2" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialog = false">បោះបង់</el-button>
      <el-button type="primary" :loading="saving" :disabled="!ready.length || !target" @click="save">
        រក្សាទុក ({{ num(ready.length) }} នាក់)
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.msg { font-size: 12px; line-height: 1.5; margin-top: 2px; }
.msg.error { color: var(--el-color-danger); }
.msg.warn { color: var(--el-color-warning-dark-2); }
.small { font-size: 12px; }
</style>
