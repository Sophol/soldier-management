<script setup>
// Update ស័ក្តិ និងមុខតំណែង: the rank, position and/or unit (and their dates) of many soldiers at once, entered by
// military ID (អត្តលេខ), from an incoming document (ឯកសារចូល). Values chosen "for all" go to every soldier listed
// and each row can still be changed; an empty value keeps the soldier's own. The server checks every row as it
// changes (errors stop saving; warnings are only shown); saving writes a history row per soldier.
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '@/api/http'
import { useLookups } from '@/stores/lookups'
import DocumentSelect from '@/components/DocumentSelect.vue'
import SoldierSelect from '@/components/SoldierSelect.vue'
import UnitTreeSelect from '@/components/UnitTreeSelect.vue'
import { fmtDate, num } from '@/utils/format'

const lookups = useLookups()
const STATUS = {
  ok: ['success', 'ត្រឹមត្រូវ'], warning: ['warning', 'ត្រឹមត្រូវ (មានការព្រមាន)'], unchanged: ['info', 'គ្មានការផ្លាស់ប្ដូរ'],
  error: ['danger', 'មិនអាច'], not_found: ['danger', 'រកមិនឃើញ'],
}
const FIELDS = ['rank_id', 'rank_date', 'position_id', 'position_date', 'unit_id', 'unit_date']

const ranks = computed(() => [...lookups.list('ranks')].sort((a, b) => (b.sort_order ?? 0) - (a.sort_order ?? 0)))
const positions = computed(() => lookups.list('positions').filter((p) => p.active !== false))
const ids = ref('')
const picked = ref(null)
const rows = ref([])
const checking = ref(false)
const saving = ref(false)
const all = reactive({ rank_id: null, rank_date: null, position_id: null, position_date: null, unit_id: null, unit_date: null })
const doc = reactive({ incoming_document_id: null, note: null })
const ready = computed(() => rows.value.filter((r) => ['ok', 'warning'].includes(r.status)))
const blocked = computed(() => rows.value.filter((r) => ['error'].includes(r.status)))

const values = (r) => Object.fromEntries(FIELDS.map((k) => [k, r[k] ?? null]))
const items = () => rows.value.filter((r) => r.soldier_id).map((r) => ({ soldier_id: r.soldier_id, ...values(r) }))

let seq = 0
// checks the rows listed (with their values) and the IDs added (they get the values "for all")
async function check(text = '') {
  if (!text.trim() && !rows.value.some((r) => r.soldier_id)) return
  const mine = ++seq
  checking.value = true
  try {
    const { data } = await http.post('/rank-position-updates/check', { military_ids: text, defaults: { ...all }, items: items() })
    if (mine !== seq) return // a newer check is on its way
    rows.value = data
    if (text) ids.value = ''
  } finally {
    if (mine === seq) checking.value = false
  }
}
let timer = null
function recheck() {
  clearTimeout(timer)
  timer = setTimeout(() => check(), 400)
}
function setCell(row, key, value) {
  row[key] = value ?? null
  recheck()
}

async function applyAll() {
  const given = FIELDS.filter((k) => all[k])
  if (!given.length) return ElMessage.warning('សូមជ្រើសរើសឋានន្តរស័ក្តិ មុខតំណែង អង្គភាព ឬថ្ងៃខែឆ្នាំ ជាមុនសិន')
  rows.value.forEach((r) => { if (r.soldier_id) given.forEach((k) => { r[k] = all[k] }) })
  await check()
}

function addPicked(s) {
  picked.value = null
  if (s) check(s.military_id)
}
function removeRow(i) { rows.value.splice(i, 1) }
function clearAll() { rows.value = []; ids.value = '' }

const changedCell = (row, key) => row.changed?.includes(key)
const currentText = (row, key) => {
  const c = row.current || {}
  if (key === 'rank_id') return lookups.name('ranks', c.rank_id) || '-'
  if (key === 'position_id') return lookups.name('positions', c.position_id) || '-'
  if (key === 'unit_id') return row.current_unit_name || '-'
  return fmtDate(c[key]) || '-'
}

async function save() {
  if (blocked.value.length) return ElMessage.warning(`មាន ${num(blocked.value.length)} នាក់ «មិនអាច» — សូមកែ ឬដកចេញពីបញ្ជីជាមុនសិន`)
  if (!ready.value.length) return ElMessage.warning('មិនមានយោធិនដែលត្រូវ Update')
  if (!doc.incoming_document_id) {
    try {
      await ElMessageBox.confirm('មិនទាន់ភ្ជាប់ឯកសារចូល។ បន្តរក្សាទុកដែរឬទេ?', 'បញ្ជាក់', { type: 'warning', confirmButtonText: 'បន្ត', cancelButtonText: 'ត្រឡប់' })
    } catch { return }
  }
  saving.value = true
  try {
    const { data } = await http.post('/rank-position-updates', {
      incoming_document_id: doc.incoming_document_id, note: doc.note || null,
      items: ready.value.map((r) => ({ soldier_id: r.soldier_id, ...values(r) })),
    })
    ElMessage.success(`បាន Update ស័ក្តិ និងមុខតំណែង ${num(data.saved)} នាក់`)
    rows.value = []
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="page">
    <div class="page-head" style="margin-bottom: 12px">
      <h2>Update ស័ក្តិ និងមុខតំណែង</h2>
    </div>

    <el-card shadow="never">
      <el-form label-position="top">
        <el-row :gutter="12">
          <el-col :md="12"><el-form-item label="ឯកសារចូល">
            <DocumentSelect v-model="doc.incoming_document_id" />
          </el-form-item></el-col>
          <el-col :md="12"><el-form-item label="កំណត់សម្គាល់">
            <el-input v-model="doc.note" maxlength="300" />
          </el-form-item></el-col>
        </el-row>

        <div class="section">សម្រាប់យោធិនទាំងអស់ (ទុកទំនេរ = រក្សាតម្លៃរបស់យោធិន)</div>
        <el-row :gutter="12">
          <el-col :md="6"><el-form-item label="ឋានន្តរស័ក្តិ">
            <el-select v-model="all.rank_id" clearable filterable style="width: 100%">
              <el-option v-for="r in ranks" :key="r.id" :value="r.id" :label="r.name_kh" />
            </el-select>
          </el-form-item></el-col>
          <el-col :md="6"><el-form-item label="ថ្ងៃខែឆ្នាំឡើងស័ក្តិ">
            <el-date-picker v-model="all.rank_date" type="date" value-format="YYYY-MM-DD" format="DD/MM/YYYY" placeholder="ថ្ងៃ/ខែ/ឆ្នាំ" style="width: 100%" />
          </el-form-item></el-col>
          <el-col :md="6"><el-form-item label="មុខតំណែង">
            <el-select v-model="all.position_id" clearable filterable style="width: 100%">
              <el-option v-for="p in positions" :key="p.id" :value="p.id" :label="p.name_kh" />
            </el-select>
          </el-form-item></el-col>
          <el-col :md="6"><el-form-item label="ថ្ងៃខែឆ្នាំមុខតំណែង">
            <el-date-picker v-model="all.position_date" type="date" value-format="YYYY-MM-DD" format="DD/MM/YYYY" placeholder="ថ្ងៃ/ខែ/ឆ្នាំ" style="width: 100%" />
          </el-form-item></el-col>
          <el-col :md="12"><el-form-item label="អង្គភាព (ក្នុងករណីផ្លាស់ប្ដូរអង្គភាព)">
            <UnitTreeSelect v-model="all.unit_id" />
          </el-form-item></el-col>
          <el-col :md="6"><el-form-item label="ថ្ងៃខែឆ្នាំផ្លាស់អង្គភាព">
            <el-date-picker v-model="all.unit_date" type="date" value-format="YYYY-MM-DD" format="DD/MM/YYYY" placeholder="ថ្ងៃ/ខែ/ឆ្នាំ" style="width: 100%" />
          </el-form-item></el-col>
        </el-row>

        <el-row :gutter="12">
          <el-col :md="14"><el-form-item label="អត្តលេខ (មួយ ឬច្រើន — មួយបន្ទាត់មួយ ឬបំបែកដោយក្បៀស)">
            <el-input v-model="ids" type="textarea" :rows="3" placeholder="000652&#10;088601, 023840" />
          </el-form-item></el-col>
          <el-col :md="10">
            <el-form-item label="ឬស្វែងរកតាមឈ្មោះ"><SoldierSelect v-model="picked" @select="addPicked" /></el-form-item>
            <el-button type="primary" plain icon="Search" :loading="checking" @click="check(ids)">បញ្ចូលអត្តលេខ</el-button>
            <el-button v-if="rows.length" icon="Check" @click="applyAll">អនុវត្តលើទាំងអស់</el-button>
            <el-button v-if="rows.length" icon="Delete" @click="clearAll">សម្អាត</el-button>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-card v-if="rows.length" shadow="never" style="margin-top: 12px">
      <el-table v-loading="checking" :data="rows" border size="small" max-height="560">
        <el-table-column type="index" label="ល.រ" width="55" fixed />
        <el-table-column prop="military_id" label="អត្តលេខ" width="85" fixed />
        <el-table-column prop="soldier_name" label="គោត្តនាមនិងនាម" min-width="140" fixed />
        <el-table-column label="ឋានន្តរស័ក្តិ" width="190">
          <template #default="{ row }">
            <template v-if="row.soldier_id">
              <el-select :model-value="row.rank_id" clearable filterable size="small" :class="{ changed: changedCell(row, 'rank_id') }" @update:model-value="(v) => setCell(row, 'rank_id', v)">
                <el-option v-for="r in ranks" :key="r.id" :value="r.id" :label="r.name_kh" />
              </el-select>
              <div v-if="changedCell(row, 'rank_id')" class="was">មុន៖ {{ currentText(row, 'rank_id') }}</div>
            </template>
          </template>
        </el-table-column>
        <el-table-column label="ថ្ងៃឡើងស័ក្តិ" width="150">
          <template #default="{ row }">
            <template v-if="row.soldier_id">
              <el-date-picker :model-value="row.rank_date" type="date" size="small" value-format="YYYY-MM-DD" format="DD/MM/YYYY" style="width: 100%" :class="{ changed: changedCell(row, 'rank_date') }" @update:model-value="(v) => setCell(row, 'rank_date', v)" />
              <div v-if="changedCell(row, 'rank_date')" class="was">មុន៖ {{ currentText(row, 'rank_date') }}</div>
            </template>
          </template>
        </el-table-column>
        <el-table-column label="មុខតំណែង" width="200">
          <template #default="{ row }">
            <template v-if="row.soldier_id">
              <el-select :model-value="row.position_id" clearable filterable size="small" :class="{ changed: changedCell(row, 'position_id') }" @update:model-value="(v) => setCell(row, 'position_id', v)">
                <el-option v-for="p in positions" :key="p.id" :value="p.id" :label="p.name_kh" />
              </el-select>
              <div v-if="changedCell(row, 'position_id')" class="was">មុន៖ {{ currentText(row, 'position_id') }}</div>
            </template>
          </template>
        </el-table-column>
        <el-table-column label="ថ្ងៃមុខតំណែង" width="150">
          <template #default="{ row }">
            <template v-if="row.soldier_id">
              <el-date-picker :model-value="row.position_date" type="date" size="small" value-format="YYYY-MM-DD" format="DD/MM/YYYY" style="width: 100%" :class="{ changed: changedCell(row, 'position_date') }" @update:model-value="(v) => setCell(row, 'position_date', v)" />
              <div v-if="changedCell(row, 'position_date')" class="was">មុន៖ {{ currentText(row, 'position_date') }}</div>
            </template>
          </template>
        </el-table-column>
        <el-table-column label="អង្គភាព" width="220">
          <template #default="{ row }">
            <template v-if="row.soldier_id">
              <UnitTreeSelect :model-value="row.unit_id" size="small" :class="{ changed: changedCell(row, 'unit_id') }" @update:model-value="(v) => setCell(row, 'unit_id', v)" />
              <div v-if="changedCell(row, 'unit_id')" class="was">មុន៖ {{ currentText(row, 'unit_id') }}</div>
            </template>
          </template>
        </el-table-column>
        <el-table-column label="ថ្ងៃផ្លាស់អង្គភាព" width="150">
          <template #default="{ row }">
            <template v-if="row.soldier_id">
              <el-date-picker :model-value="row.unit_date" type="date" size="small" value-format="YYYY-MM-DD" format="DD/MM/YYYY" style="width: 100%" :class="{ changed: changedCell(row, 'unit_date') }" @update:model-value="(v) => setCell(row, 'unit_date', v)" />
              <div v-if="changedCell(row, 'unit_date')" class="was">មុន៖ {{ currentText(row, 'unit_date') }}</div>
            </template>
          </template>
        </el-table-column>
        <el-table-column label="ស្ថានភាព" min-width="200">
          <template #default="{ row }">
            <el-tag :type="STATUS[row.status][0]" size="small">{{ STATUS[row.status][1] }}</el-tag>
            <div v-for="e in row.errors" :key="`e-${e}`" class="msg error">{{ e }}</div>
            <div v-for="w in row.warnings" :key="`w-${w}`" class="msg warn">{{ w }}</div>
          </template>
        </el-table-column>
        <el-table-column width="50" align="center" fixed="right">
          <template #default="{ $index }"><el-button link type="danger" icon="Close" @click="removeRow($index)" /></template>
        </el-table-column>
      </el-table>
      <div class="foot">
        <span class="muted small">នឹង Update {{ num(ready.length) }} នាក់ ក្នុងចំណោម {{ num(rows.length) }}
          (អ្នក «គ្មានការផ្លាស់ប្ដូរ» មិនត្រូវបានប៉ះពាល់ទេ)</span>
        <el-button type="primary" icon="Check" :loading="saving" :disabled="!ready.length" @click="save">
          រក្សាទុក ({{ num(ready.length) }} នាក់)
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.section { font-weight: 600; margin: 4px 0 8px; color: var(--el-text-color-regular); }
.msg { font-size: 12px; line-height: 1.5; margin-top: 2px; }
.msg.error { color: var(--el-color-danger); }
.msg.warn { color: var(--el-color-warning-dark-2); }
.was { font-size: 11px; color: var(--el-text-color-secondary); margin-top: 2px; }
.changed :deep(.el-select__wrapper), .changed :deep(.el-input__wrapper) { box-shadow: 0 0 0 1px var(--el-color-success) inset; background: var(--el-color-success-light-9); }
.foot { display: flex; align-items: center; justify-content: space-between; margin-top: 10px; gap: 12px; flex-wrap: wrap; }
.small { font-size: 12px; }
</style>
