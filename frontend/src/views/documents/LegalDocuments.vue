<script setup>
/** ឯកសារគតិយុទ្ធ: incoming and outgoing documents counted per document type; click a count to open the list. */
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import http from '@/api/http'
import { useAuth } from '@/stores/auth'
import { num } from '@/utils/format'

const router = useRouter()
const auth = useAuth()
const year = ref(null)
const rows = ref([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    rows.value = (await http.get('/documents/by-type', { params: { year: year.value || undefined } })).data
  } finally {
    loading.value = false
  }
}

function open(direction, row) {
  const query = row.id ? { document_type_id: row.id } : {}
  router.push({ path: `/documents/${direction}`, query })
}

watch(year, load)
onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h2>ឯកសារគតិយុទ្ធ</h2>
      <div class="head-actions">
        <el-date-picker v-model="year" type="year" value-format="YYYY" placeholder="គ្រប់ឆ្នាំ" clearable style="width: 150px" />
        <el-button v-if="auth.can('doc_types.view')" icon="Setting" @click="router.push('/org/document-types')">ប្រភេទឯកសារ</el-button>
      </div>
    </div>
    <el-card shadow="never">
      <el-table v-loading="loading" :data="rows" border stripe empty-text="គ្មានទិន្នន័យ" show-summary
                :summary-method="({ data }) => ['សរុប', num(data.reduce((s, r) => s + r.incoming, 0)), num(data.reduce((s, r) => s + r.outgoing, 0))]">
        <el-table-column prop="name_kh" label="ប្រភេទឯកសារ" min-width="220" />
        <el-table-column label="ឯកសារចូល" width="160" align="center">
          <template #default="{ row }">
            <el-button link type="primary" :disabled="!row.incoming || !auth.can('doc_in.view')" @click="open('incoming', row)">{{ num(row.incoming) }}</el-button>
          </template>
        </el-table-column>
        <el-table-column label="ឯកសារចេញ" width="160" align="center">
          <template #default="{ row }">
            <el-button link type="primary" :disabled="!row.outgoing || !auth.can('doc_out.view')" @click="open('outgoing', row)">{{ num(row.outgoing) }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
