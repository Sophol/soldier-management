<script setup>
import { onMounted, reactive, ref } from 'vue'
import http from '@/api/http'
import { fmtDateTime } from '@/utils/format'

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const q = reactive({ page: 1, size: 50, table: '', action: '' })
const ACTION_TYPE = { create: 'success', update: 'warning', delete: 'danger', approve: 'success', cancel: 'danger', login: 'info' }

async function load() {
  loading.value = true
  try {
    const params = { page: q.page, size: q.size }
    if (q.table) params.table = q.table
    if (q.action) params.action = q.action
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

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head"><h2>កំណត់ហេតុសកម្មភាព</h2></div>
    <el-card shadow="never" class="filter-card">
      <el-form inline @submit.prevent="q.page = 1; load()">
        <el-form-item label="តារាង"><el-input v-model="q.table" placeholder="soldiers, decisions..." clearable /></el-form-item>
        <el-form-item label="សកម្មភាព">
          <el-select v-model="q.action" clearable style="width: 150px">
            <el-option v-for="a in ['create', 'update', 'delete', 'approve', 'cancel', 'login']" :key="a" :value="a" />
          </el-select>
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
