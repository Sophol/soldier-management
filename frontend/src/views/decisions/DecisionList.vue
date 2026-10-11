<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '@/api/http'
import { useAuth } from '@/stores/auth'
import { useLookups } from '@/stores/lookups'
import SoldierSelect from '@/components/SoldierSelect.vue'
import UnitTreeSelect from '@/components/UnitTreeSelect.vue'
import FileAttachments from '@/components/FileAttachments.vue'
import { STATUS_TAG, STATUS_TEXT, fmtDate, num } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const auth = useAuth()
const lookups = useLookups()
const kind = computed(() => route.params.kind)
const module = computed(() => `decisions_${kind.value}`)
const TITLES = { appoint: 'តែងតាំងមុខតំណែង', transfer: 'ផ្លាស់ប្ដូរមុខតំណែង / កងឯកភាព', promote: 'ដំឡើងឋានន្តរស័ក្តិ' }

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const q = reactive({ page: 1, size: 20, q: '', status: null, date_from: null, date_to: null })

const dialog = ref(false)
const saving = ref(false)
const form = ref({})
const formRef = ref()
const detail = ref(null)
const warnings = ref([])

const rules = {
  decision_no: [{ required: true, message: 'សូមបញ្ចូលលេខ' }],
  decision_date: [{ required: true, message: 'សូមបញ្ចូលថ្ងៃខែឆ្នាំ' }],
  effective_date: [{ required: true, message: 'សូមបញ្ចូលថ្ងៃចូលជាធរមាន' }],
}

async function load() {
  loading.value = true
  try {
    const params = { kind: kind.value }
    for (const [k, v] of Object.entries(q)) if (v !== null && v !== '') params[k] = v
    const { data } = await http.get('/decisions', { params })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function emptyItem() {
  return { soldier_id: null, soldier: null, new_rank_id: null, new_position_id: null, new_unit_id: null, note: '' }
}

function openCreate() {
  const today = new Date().toISOString().slice(0, 10)
  form.value = { id: null, decision_no: '', decision_date: today, effective_date: today, issued_by: '', notes: '', items: [emptyItem()] }
  warnings.value = []
  dialog.value = true
}

async function openEdit(row) {
  const { data } = await http.get(`/decisions/${row.id}`)
  form.value = {
    id: data.id, decision_no: data.decision_no, decision_date: data.decision_date, effective_date: data.effective_date,
    issued_by: data.issued_by, notes: data.notes,
    items: data.items.map((i) => ({
      soldier_id: i.soldier_id, soldier: { rank_name: i.old_rank, position_name: i.old_position, unit_name: i.old_unit },
      label: `${i.old_rank || ''} ${i.name_kh} (${i.military_id})`, new_rank_id: i.new_rank_id,
      new_position_id: i.new_position_id, new_unit_id: i.new_unit_id, note: i.note,
    })),
  }
  warnings.value = []
  dialog.value = true
}

async function save() {
  await formRef.value.validate()
  const items = form.value.items.filter((i) => i.soldier_id)
  if (!items.length) return ElMessage.warning('សូមបន្ថែមយោធិនយ៉ាងហោចណាស់ម្នាក់')
  saving.value = true
  try {
    const payload = {
      kind: kind.value, decision_no: form.value.decision_no, decision_date: form.value.decision_date,
      effective_date: form.value.effective_date, issued_by: form.value.issued_by, notes: form.value.notes,
      items: items.map(({ soldier_id, new_rank_id, new_position_id, new_unit_id, note }) => ({ soldier_id, new_rank_id, new_position_id, new_unit_id, note })),
    }
    const { data } = form.value.id ? await http.put(`/decisions/${form.value.id}`, payload) : await http.post('/decisions', payload)
    if (data.warnings?.length) {
      warnings.value = data.warnings
      ElMessage.warning('បានរក្សាទុក ប៉ុន្តែមានការព្រមាន')
      form.value.id = data.id
    } else {
      ElMessage.success('បានរក្សាទុកជាសេចក្ដីព្រាង')
      dialog.value = false
    }
    load()
  } finally {
    saving.value = false
  }
}

async function showDetail(row) {
  detail.value = (await http.get(`/decisions/${row.id}`)).data
}

async function approve(row) {
  await ElMessageBox.confirm('អនុម័តសេចក្ដីសម្រេចនេះ? ព័ត៌មានយោធិននឹងត្រូវធ្វើបច្ចុប្បន្នភាពភ្លាមៗ។', 'អនុម័ត', { type: 'warning', confirmButtonText: 'អនុម័ត' })
  await http.post(`/decisions/${row.id}/approve`)
  ElMessage.success('បានអនុម័ត')
  detail.value = null
  load()
}

async function cancel(row) {
  await ElMessageBox.confirm('លុបចោលសេចក្ដីសម្រេចនេះ? បើបានអនុម័តរួច ព័ត៌មានយោធិននឹងត្រឡប់ទៅដូចមុនវិញ។', 'លុបចោល', { type: 'warning', confirmButtonText: 'លុបចោល' })
  await http.post(`/decisions/${row.id}/cancel`)
  ElMessage.success('បានលុបចោល')
  detail.value = null
  load()
}

async function remove(row) {
  await ElMessageBox.confirm('លុបសេចក្ដីព្រាងនេះ?', 'បញ្ជាក់', { type: 'warning' })
  await http.delete(`/decisions/${row.id}`)
  load()
}

const showRank = computed(() => kind.value === 'promote')
const showPosition = computed(() => kind.value !== 'promote')
const showUnit = computed(() => kind.value !== 'promote')

function rankOptions(item) {
  const cur = item.soldier?.rank_sort
  return lookups.list('ranks').filter((r) => cur == null || r.sort_order > cur)
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h2>{{ TITLES[kind] }}</h2>
      <el-button v-if="auth.can(`${module}.create`)" type="primary" icon="Plus" @click="openCreate">បង្កើតសេចក្ដីសម្រេចថ្មី</el-button>
    </div>

    <el-card shadow="never" class="filter-card">
      <el-form inline @submit.prevent="q.page = 1; load()">
        <el-form-item><el-input v-model="q.q" placeholder="លេខ / ឈ្មោះ / អត្តលេខ" clearable prefix-icon="Search" /></el-form-item>
        <el-form-item label="ស្ថានភាព">
          <el-select v-model="q.status" clearable style="width: 140px">
            <el-option v-for="(t, k) in STATUS_TEXT" :key="k" :value="k" :label="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="ចាប់ពី"><el-date-picker v-model="q.date_from" value-format="YYYY-MM-DD" format="DD/MM/YYYY" style="width: 150px" /></el-form-item>
        <el-form-item label="ដល់"><el-date-picker v-model="q.date_to" value-format="YYYY-MM-DD" format="DD/MM/YYYY" style="width: 150px" /></el-form-item>
        <el-form-item><el-button type="primary" native-type="submit" icon="Search">ស្វែងរក</el-button></el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="rows" stripe border empty-text="គ្មានទិន្នន័យ" @row-dblclick="showDetail">
        <el-table-column type="index" label="ល.រ" width="60" :index="(i) => num((q.page - 1) * q.size + i + 1)" />
        <el-table-column prop="decision_no" label="លេខសេចក្ដីសម្រេច" width="160" />
        <el-table-column label="ថ្ងៃខែឆ្នាំ" width="120"><template #default="{ row }">{{ fmtDate(row.decision_date) }}</template></el-table-column>
        <el-table-column label="ចូលជាធរមាន" width="120"><template #default="{ row }">{{ fmtDate(row.effective_date) }}</template></el-table-column>
        <el-table-column label="ចំនួនយោធិន" width="110" align="center"><template #default="{ row }">{{ num(row.item_count) }}</template></el-table-column>
        <el-table-column prop="issued_by" label="ចេញដោយ" min-width="140" />
        <el-table-column prop="notes" label="កំណត់សម្គាល់" min-width="160" show-overflow-tooltip />
        <el-table-column label="ស្ថានភាព" width="120">
          <template #default="{ row }"><el-tag :type="STATUS_TAG[row.status]" size="small">{{ STATUS_TEXT[row.status] }}</el-tag></template>
        </el-table-column>
        <el-table-column label="សកម្មភាព" width="220" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" icon="View" @click="showDetail(row)" />
            <el-button link icon="Printer" @click="router.push(`/decisions/${row.id}/print`)" />
            <template v-if="row.status === 'draft'">
              <el-button v-if="auth.can(`${module}.update`)" link type="primary" icon="Edit" @click="openEdit(row)" />
              <el-button v-if="auth.can(`${module}.approve`)" link type="success" icon="Select" @click="approve(row)">អនុម័ត</el-button>
              <el-button v-if="auth.can(`${module}.delete`)" link type="danger" icon="Delete" @click="remove(row)" />
            </template>
            <el-button v-else-if="row.status === 'approved' && auth.can(`${module}.approve`)" link type="danger" icon="CircleClose" @click="cancel(row)">លុបចោល</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="q.page" v-model:page-size="q.size" class="pager" background
                     layout="total, prev, pager, next" :total="total" @current-change="load" />
    </el-card>

    <!-- create / edit -->
    <el-dialog v-model="dialog" :title="(form.id ? 'កែប្រែ' : 'បង្កើត') + ' សេចក្ដីសម្រេច ' + TITLES[kind]" width="1100px"
               :close-on-click-modal="false" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-row :gutter="14">
          <el-col :span="6"><el-form-item label="លេខសេចក្ដីសម្រេច / ប្រកាស" prop="decision_no"><el-input v-model="form.decision_no" /></el-form-item></el-col>
          <el-col :span="5"><el-form-item label="ថ្ងៃខែឆ្នាំ" prop="decision_date"><el-date-picker v-model="form.decision_date" value-format="YYYY-MM-DD" format="DD/MM/YYYY" style="width: 100%" /></el-form-item></el-col>
          <el-col :span="5"><el-form-item label="ចូលជាធរមានពីថ្ងៃ" prop="effective_date"><el-date-picker v-model="form.effective_date" value-format="YYYY-MM-DD" format="DD/MM/YYYY" style="width: 100%" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="ចេញដោយ"><el-input v-model="form.issued_by" /></el-form-item></el-col>
        </el-row>
        <el-alert v-for="w in warnings" :key="w" :title="w" type="warning" show-icon :closable="false" style="margin-bottom: 6px" />
        <el-table :data="form.items" border size="small">
          <el-table-column label="យោធិន" min-width="260">
            <template #default="{ row }">
              <SoldierSelect v-model="row.soldier_id" :initial-label="row.label" @select="(s) => (row.soldier = s)" />
            </template>
          </el-table-column>
          <el-table-column label="បច្ចុប្បន្ន" min-width="200">
            <template #default="{ row }">
              <div v-if="row.soldier" class="small">
                <div>{{ row.soldier.rank_name }}</div>
                <div class="muted">{{ row.soldier.position_name }} · {{ row.soldier.unit_name }}</div>
              </div>
            </template>
          </el-table-column>
          <el-table-column v-if="showRank" label="ឋានន្តរស័ក្តិថ្មី" width="190">
            <template #default="{ row }">
              <el-select v-model="row.new_rank_id" filterable>
                <el-option v-for="r in rankOptions(row)" :key="r.id" :value="r.id" :label="r.name_kh" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column v-if="showPosition" label="មុខតំណែងថ្មី" width="190">
            <template #default="{ row }">
              <el-select v-model="row.new_position_id" filterable clearable>
                <el-option v-for="p in lookups.list('positions')" :key="p.id" :value="p.id" :label="p.name_kh" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column v-if="showUnit" label="អង្គភាពថ្មី" width="220">
            <template #default="{ row }"><UnitTreeSelect v-model="row.new_unit_id" /></template>
          </el-table-column>
          <el-table-column label="កំណត់សម្គាល់" width="150"><template #default="{ row }"><el-input v-model="row.note" /></template></el-table-column>
          <el-table-column width="50"><template #default="{ $index }"><el-button link type="danger" icon="Delete" @click="form.items.splice($index, 1)" /></template></el-table-column>
        </el-table>
        <el-button icon="Plus" size="small" style="margin-top: 8px" @click="form.items.push(emptyItem())">បន្ថែមយោធិន</el-button>
        <el-form-item label="កំណត់សម្គាល់" style="margin-top: 12px"><el-input v-model="form.notes" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">បិទ</el-button>
        <el-button type="primary" :loading="saving" @click="save">រក្សាទុកជាសេចក្ដីព្រាង</el-button>
      </template>
    </el-dialog>

    <!-- detail -->
    <el-drawer :model-value="!!detail" size="70%" :title="detail ? `សេចក្ដីសម្រេចលេខ ${detail.decision_no}` : ''" @close="detail = null">
      <template v-if="detail">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="ប្រភេទ">{{ detail.kind_name }}</el-descriptions-item>
          <el-descriptions-item label="ថ្ងៃខែឆ្នាំ">{{ fmtDate(detail.decision_date) }}</el-descriptions-item>
          <el-descriptions-item label="ចូលជាធរមាន">{{ fmtDate(detail.effective_date) }}</el-descriptions-item>
          <el-descriptions-item label="ស្ថានភាព"><el-tag :type="STATUS_TAG[detail.status]">{{ STATUS_TEXT[detail.status] }}</el-tag></el-descriptions-item>
          <el-descriptions-item label="ចេញដោយ" :span="2">{{ detail.issued_by }}</el-descriptions-item>
          <el-descriptions-item label="កំណត់សម្គាល់" :span="3">{{ detail.notes }}</el-descriptions-item>
        </el-descriptions>
        <el-table :data="detail.items" border size="small" style="margin-top: 14px">
          <el-table-column type="index" label="ល.រ" width="55" />
          <el-table-column prop="military_id" label="អត្តលេខ" width="100" />
          <el-table-column prop="name_kh" label="គោត្តនាមនិងនាម" min-width="140" />
          <el-table-column v-if="detail.kind === 'promote'" label="ឋានន្តរស័ក្តិ" min-width="200"><template #default="{ row }">{{ row.old_rank }} → <b>{{ row.new_rank }}</b></template></el-table-column>
          <el-table-column v-if="detail.kind !== 'promote'" label="មុខតំណែង" min-width="200"><template #default="{ row }"><span v-if="row.new_position_id">{{ row.old_position || '-' }} → <b>{{ row.new_position }}</b></span></template></el-table-column>
          <el-table-column v-if="detail.kind !== 'promote'" label="អង្គភាព" min-width="200"><template #default="{ row }"><span v-if="row.new_unit_id">{{ row.old_unit || '-' }} → <b>{{ row.new_unit }}</b></span></template></el-table-column>
          <el-table-column prop="note" label="កំណត់សម្គាល់" />
        </el-table>
        <div class="section-title">ឯកសារភ្ជាប់</div>
        <FileAttachments owner-type="decision" :owner-id="detail.id" :editable="auth.can(`${module}.update`)" />
        <div class="drawer-actions">
          <el-button icon="Printer" @click="router.push(`/decisions/${detail.id}/print`)">បោះពុម្ព</el-button>
          <el-button v-if="detail.status === 'draft' && auth.can(`${module}.approve`)" type="success" icon="Select" @click="approve(detail)">អនុម័ត</el-button>
          <el-button v-if="detail.status === 'approved' && auth.can(`${module}.approve`)" type="danger" icon="CircleClose" @click="cancel(detail)">លុបចោល</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.small { font-size: 12px; line-height: 1.6; }
.drawer-actions { margin-top: 18px; display: flex; gap: 8px; }
</style>
