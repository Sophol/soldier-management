<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import http from '@/api/http'
import CrudPage from '@/components/CrudPage.vue'
import { lookupConfig } from '@/crud-configs'

const route = useRoute()
const categories = ref([])
const category = ref(route.query.category || 'soldier_status')
// the menu links straight to a category (ផ្នែក, កម្រិតវប្បធម៌): follow the URL when it changes
watch(() => route.query.category, (c) => { if (c) category.value = c })

onMounted(async () => { categories.value = (await http.get('/meta/lookup-categories')).data })

const config = computed(() => lookupConfig(category.value, categories.value.find((c) => c.value === category.value)?.label || ''))
</script>

<template>
  <div>
    <div class="cats">
      <el-radio-group v-model="category" size="small">
        <el-radio-button v-for="c in categories" :key="c.value" :value="c.value">{{ c.label }}</el-radio-button>
      </el-radio-group>
    </div>
    <el-alert v-if="category === 'soldier_status'" class="note" type="warning" :closable="false" show-icon
              title="កូដ active / retired / category2 / separated ត្រូវបានប្រើដោយប្រព័ន្ធ — សូមកុំកែប្រែ ឬលុបកូដទាំងនេះ។" />
    <CrudPage :config="config" />
  </div>
</template>

<style scoped>
.cats { padding: 20px 20px 0; }
.note { margin: 12px 20px 0; width: auto; }
</style>
