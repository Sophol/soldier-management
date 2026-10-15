<script setup>
/** Youth doing military service: list, search and filters (status / year / province), add and edit. */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import http from '@/api/http'
import CrudPage from '@/components/CrudPage.vue'
import { conscriptConfig } from '@/conscript-configs'

const router = useRouter()
const meta = ref(null)
const provinces = ref([])

onMounted(async () => {
  const [m, p] = await Promise.all([http.get('/meta/conscription'), http.get('/geo/provinces', { params: { size: 100 } })])
  meta.value = m.data
  provinces.value = p.data.items.map((x) => ({ value: x.id, label: `${x.type}${x.name_kh}` }))
})

const config = computed(() => conscriptConfig(meta.value, provinces.value))
</script>

<template>
  <CrudPage v-if="meta" :config="config">
    <template #row-actions="{ row }">
      <el-button link type="primary" icon="View" @click="router.push(`/conscripts/${row.id}`)" />
    </template>
  </CrudPage>
</template>
