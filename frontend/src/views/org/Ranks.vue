<script setup>
import { computed } from 'vue'
import CrudPage from '@/components/CrudPage.vue'
import { useLookups } from '@/stores/lookups'

const lookups = useLookups()
const classOptions = () => lookups.list('rank_classes').map((c) => ({ value: c.id, label: c.name_kh }))

const config = computed(() => ({
  title: 'ឋានន្តរស័ក្តិ', endpoint: '/ranks', module: 'ranks', refreshLookups: true,
  columns: [
    { key: 'rank_class_name', label: 'ថ្នាក់', width: 140 },
    { key: 'name_kh', label: 'ឋានន្តរស័ក្តិ', minWidth: 160 },
    { key: 'name_en', label: 'English', minWidth: 140 },
    { key: 'short_kh', label: 'អក្សរកាត់', width: 100 },
    { key: 'sort_order', label: 'លំដាប់ (ខ្ពស់ = ធំ)', width: 150 },
    { key: 'min_years_to_next', label: 'ឆ្នាំអប្បបរមាដើម្បីឡើង', width: 170 },
    { key: 'active', label: 'ស្ថានភាព', width: 90, value: (r) => (r.active ? 'សកម្ម' : 'អសកម្ម'), tag: (r) => (r.active ? 'success' : 'info') },
  ],
  filters: [{ key: 'rank_class_id', label: 'ថ្នាក់', type: 'select', options: classOptions }],
  fields: [
    { key: 'rank_class_id', label: 'ថ្នាក់ (នាយទាហាន / នាយទាហានរង / ពលទាហាន)', type: 'select', required: true, options: classOptions },
    { key: 'name_kh', label: 'ឋានន្តរស័ក្តិ (ខ្មែរ)', required: true, span: 12 },
    { key: 'name_en', label: 'ឋានន្តរស័ក្តិ (អង់គ្លេស)', span: 12 },
    { key: 'short_kh', label: 'អក្សរកាត់', span: 8 },
    { key: 'sort_order', label: 'លំដាប់ (ខ្ពស់ = ឋានៈធំ)', type: 'number', default: 0, span: 8 },
    { key: 'min_years_to_next', label: 'ឆ្នាំអប្បបរមាដើម្បីឡើងបន្ទាប់', type: 'number', span: 8 },
    { key: 'active', label: 'សកម្ម', type: 'switch', default: true },
  ],
}))
</script>

<template>
  <el-alert class="rank-note" type="warning" show-icon :closable="false"
            title="បញ្ជីឋានន្តរស័ក្តិដើមគឺជាសេចក្ដីព្រាង — សូមពិនិត្យ និងកែតម្រូវតាមបទដ្ឋានផ្លូវការ។ 'ឆ្នាំអប្បបរមា' ប្រើសម្រាប់ការជូនដំណឹងដំឡើងស័ក្តិ។" />
  <CrudPage :config="config" />
</template>

<style scoped>
.rank-note { margin: 20px 20px 0; width: auto; }
</style>
