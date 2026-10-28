<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import http from '@/api/http'
import { useLookups } from '@/stores/lookups'
import { fmtDateTime } from '@/utils/format'

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const q = reactive({ page: 1, size: 50, table: '', action: '', user_id: null, record_id: '', date_from: null, date_to: null })
const ACTION_TYPE = { create: 'success', update: 'warning', delete: 'danger', approve: 'success', cancel: 'danger', login: 'info' }
const ACTIONS = ['create', 'update', 'delete', 'submit', 'approve', 'return', 'reject', 'cancel', 'import', 'export', 'login']
const users = ref([])
const dates = computed({
  get: () => (q.date_from || q.date_to ? [q.date_from, q.date_to] : null),
  set: (v) => { q.date_from = v?.[0] || null; q.date_to = v?.[1] || null },
})

async function load() {
  loading.value = true
  try {
    const params = { page: q.page, size: q.size }
    for (const k of ['table', 'action', 'user_id', 'record_id', 'date_from', 'date_to']) if (q[k]) params[k] = q[k]
    const { data } = await http.get('/audit-logs', { params })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function changes(row) {
  if (!row.before || !row.after) return ''
  return Object.keys(row.after)
    .filter((k) => !['updated_at', 'updated_by'].includes(k) && JSON.stringify(row.before[k]) !== JSON.stringify(row.after[k]))
    .map((k) => `${k}: ${row.before[k] ?? '∅'} → ${row.after[k] ?? '∅'}`).join('\n')
}

onMounted(async () => {
  load()
  users.value = await useLookups().loadUsers()
})
</script>

<template>
  <div class="page">
    <div class="page-head"><h2>កំណត់ហេតុសកម្មភាព</h2></div>
    <el-card shadow="never" class="filter-card">
      <el-form inline @submit.prevent="q.page = 1; load()">
        <el-form-item label="តារាង"><el-input v-model="q.table" placeholder="soldiers, decisions..." clearable /></el-form-item>
        <el-form-item label="ID"><el-input v-model="q.record_id" clearable style="width: 100px" /></el-form-item>
        <el-form-item label="សកម្មភាព">
          <el-select v-model="q.action" clearable style="width: 150px">
            <el-option v-for="a in ACTIONS" :key="a" :value="a" />
          </el-select>
        </el-form-item>
        <el-form-item label="អ្នកប្រើ">
          <el-select v-model="q.user_id" clearable filterable style="width: 180px">
            <el-option v-for="u in users" :key="u.id" :value="u.id" :label="`${u.full_name} (${u.username})`" />
          </el-select>
        </el-form-item>
        <el-form-item label="ថ្ងៃ">
          <el-date-picker v-model="dates" type="daterange" value-format="YYYY-MM-DD" format="DD/MM/YYYY"
                          start-placeholder="ពីថ្ងៃ" end-placeholder="ដល់ថ្ងៃ" style="width: 260px" />
        </el-form-item>
        <el-form-item><el-button type="primary" native-type="submit" icon="Search">ស្វែងរក</el-button></el-form-item>
      </el-form>
    </el-card>
    <el-card shadow="never">
      <el-table v-loading="loading" :data="rows" border size="small" empty-text="គ្មានទិន្នន័យ">
        <el-table-column label="ពេលវេលា" width="150"><template #default="{ row }">{{ fmtDateTime(row.created_at) }}</template></el-table-column>
        <el-table-column prop="username" label="អ្នកប្រើ" width="120" />
        <el-table-column label="សកម្មភាព" width="130"><template #default="{ row }"><el-tag size="small" :type="ACTION_TYPE[row.action] || 'info'">{{ row.action }}</el-tag></template></el-table-column>
        <el-table-column prop="table_name" label="តារាង" width="160" />
        <el-table-column prop="record_id" label="ID" width="80" />
        <el-table-column label="ការផ្លាស់ប្ដូរ" min-width="300"><template #default="{ row }"><pre class="diff">{{ changes(row) }}</pre></template></el-table-column>
        <el-table-column prop="ip" label="IP" width="120" />
      </el-table>
      <el-pagination v-model:current-page="q.page" class="pager" background layout="total, prev, pager, next"
                     :page-size="q.size" :total="total" @current-change="load" />
    </el-card>
  </div>
</template>

<style scoped>
.diff { margin: 0; white-space: pre-wrap; font-family: inherit; font-size: 12px; max-height: 120px; overflow: auto; }
</style>
