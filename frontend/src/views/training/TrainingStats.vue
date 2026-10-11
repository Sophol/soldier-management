<script setup>
/** Education level / specialty overview: soldier counts per value, linking to the filtered soldier list. */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import http from '@/api/http'
import { useLookups } from '@/stores/lookups'
import { num } from '@/utils/format'

const props = defineProps({ by: { type: String, required: true } })
const router = useRouter()
const lookups = useLookups()
const counts = ref({})
const loading = ref(true)

const meta = computed(() => (props.by === 'education'
  ? { title: 'កម្រិតវប្បធម៌', list: lookups.list('education_level'), param: 'education_level_id', manage: '/settings/lookups?category=education_level' }
  : { title: 'ជំនាញឯកទេស', list: lookups.list('specialties'), param: 'specialty_id', manage: '/org/specialties' }))

onMounted(async () => {
  try {
    const results = await Promise.all(meta.value.list.map((item) => http.get('/soldiers', { params: { [meta.value.param]: item.id, size: 1 } })
      .then((r) => [item.id, r.data.total])))
    counts.value = Object.fromEntries(results)
  } finally {
    loading.value = false
  }
})

const rows = computed(() => meta.value.list.map((i) => ({ ...i, count: counts.value[i.id] ?? 0 })))
const total = computed(() => rows.value.reduce((s, r) => s + r.count, 0))
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h2>{{ meta.title }}</h2>
      <el-button icon="Setting" @click="router.push(meta.manage)">គ្រប់គ្រងបញ្ជី{{ meta.title }}</el-button>
    </div>
    <el-card v-loading="loading" shadow="never">
      <el-table :data="rows" border stripe empty-text="គ្មានទិន្នន័យ" show-summary :summary-method="() => ['', 'សរុប', num(total), '']">
        <el-table-column type="index" label="ល.រ" width="60" />
        <el-table-column prop="name_kh" :label="meta.title" />
        <el-table-column label="ចំនួនយោធិន" width="160" align="center"><template #default="{ row }">{{ num(row.count) }}</template></el-table-column>
        <el-table-column width="160" align="center">
          <template #default="{ row }">
            <el-button link type="primary" icon="View" @click="router.push({ path: '/soldiers', query: { [meta.param]: row.id } })">មើលបញ្ជី</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
