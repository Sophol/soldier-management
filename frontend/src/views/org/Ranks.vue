<script setup>
import { computed } from 'vue'
import CrudPage from '@/components/CrudPage.vue'
import { useLookups } from '@/stores/lookups'

const lookups = useLookups()
const classOptions = () => lookups.list('rank_classes').map((c) => ({ value: c.id, label: c.name_kh }))
const BRANCH = { army: 'ជើងគោក', navy: 'ជើងទឹក', all: 'ទាំងពីរ' }
const branchOptions = Object.entries(BRANCH).map(([value, label]) => ({ value, label }))
const money = (v) => (v == null ? '' : Number(v).toLocaleString('en-US'))

const config = computed(() => ({
  title: 'ឋានន្តរស័ក្តិ', endpoint: '/ranks', module: 'ranks', refreshLookups: true,
  columns: [
    { key: 'rank_class_name', label: 'ថ្នាក់', width: 140 },
    { key: 'branch', label: 'ប្រភេទ', width: 100, value: (r) => BRANCH[r.branch] },
    { key: 'name_kh', label: 'ឋានន្តរស័ក្តិ', minWidth: 160 },
    { key: 'name_en', label: 'English', minWidth: 140 },
    { key: 'short_kh', label: 'អក្សរកាត់', width: 100 },
    { key: 'sort_order', label: 'លំដាប់ (ខ្ពស់ = ធំ)', width: 150 },
    { key: 'min_years_to_next', label: 'ឆ្នាំអប្បបរមាដើម្បីឡើង', width: 170 },
    { key: 'quota', label: 'ចំនួនកំណត់ / កំពុងមាន', width: 170, value: (r) => (r.quota == null ? r.filled : `${r.quota} / ${r.filled}`) },
    { key: 'retirement_age', label: 'អាយុសោធននិវត្តន៍', width: 140 },
    { key: 'salary', label: 'ប្រាក់បៀវត្ស (រៀល)', width: 150, value: (r) => money(r.salary) },
    { key: 'active', label: 'ស្ថានភាព', width: 90, value: (r) => (r.active ? 'សកម្ម' : 'អសកម្ម'), tag: (r) => (r.active ? 'success' : 'info') },
  ],
  filters: [{ key: 'rank_class_id', label: 'ថ្នាក់', type: 'select', options: classOptions },
    { key: 'branch', label: 'ប្រភេទ', type: 'select', options: branchOptions, width: '140px' }],
  fields: [
    { key: 'rank_class_id', label: 'ថ្នាក់ (នាយទាហាន / នាយទាហានរង / ពលទាហាន)', type: 'select', required: true, options: classOptions, span: 16 },
    { key: 'branch', label: 'ប្រភេទស័ក្តិ (ជើងគោក / ជើងទឹក)', type: 'select', required: true, default: 'army', options: branchOptions, span: 8 },
    { key: 'name_kh', label: 'ឋានន្តរស័ក្តិ (ខ្មែរ)', required: true, span: 12 },
    { key: 'name_en', label: 'ឋានន្តរស័ក្តិ (អង់គ្លេស)', span: 12 },
    { key: 'short_kh', label: 'អក្សរកាត់', span: 8 },
    { key: 'sort_order', label: 'លំដាប់ (ខ្ពស់ = ឋានៈធំ)', type: 'number', default: 0, span: 8 },
    { key: 'min_years_to_next', label: 'ឆ្នាំអប្បបរមាដើម្បីឡើងបន្ទាប់', type: 'number', span: 8 },
    { key: 'quota', label: 'ចំនួនកំណត់ (ទុកទំនេរ = គ្មានកំណត់)', type: 'number', span: 8 },
    { key: 'retirement_age', label: 'អាយុសោធននិវត្តន៍ (ទុកទំនេរ = តាមការកំណត់ប្រព័ន្ធ)', type: 'number', span: 8 },
    { key: 'salary', label: 'ប្រាក់បៀវត្ស (រៀល)', type: 'number', span: 8 },
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
