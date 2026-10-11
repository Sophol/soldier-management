<script setup>
/** Drill-down: province -> districts -> communes -> villages. */
import { computed, ref } from 'vue'
import CrudPage from '@/components/CrudPage.vue'
import { geoConfig } from '@/crud-configs'

const trail = ref([]) // [{ level, id, name }]
const LEVELS = ['provinces', 'districts', 'communes', 'villages']
const PARENT = { districts: 'province_id', communes: 'district_id', villages: 'commune_id' }

const level = computed(() => LEVELS[trail.value.length])
const config = computed(() => {
  const parent = trail.value[trail.value.length - 1]
  const cfg = geoConfig(level.value, PARENT[level.value], parent?.id)
  if (parent) cfg.defaults = { [PARENT[level.value]]: parent.id }
  return cfg
})

function drill(row) {
  trail.value = [...trail.value, { id: row.id, name: `${row.type || ''}${row.name_kh}` }]
}
</script>

<template>
  <div>
    <div class="crumbs">
      <el-breadcrumb separator="›">
        <el-breadcrumb-item><el-link @click="trail = []">ប្រទេសកម្ពុជា</el-link></el-breadcrumb-item>
        <el-breadcrumb-item v-for="(t, i) in trail" :key="t.id">
          <el-link @click="trail = trail.slice(0, i + 1)">{{ t.name }}</el-link>
        </el-breadcrumb-item>
      </el-breadcrumb>
    </div>
    <CrudPage :key="level + (trail.at(-1)?.id || '')" :config="config">
      <template v-if="level !== 'villages'" #row-actions="{ row }">
        <el-tooltip content="មើលខាងក្រោម"><el-button link type="primary" icon="ArrowRightBold" @click="drill(row)" /></el-tooltip>
      </template>
    </CrudPage>
  </div>
</template>

<style scoped>
.crumbs { padding: 20px 20px 0; }
</style>
