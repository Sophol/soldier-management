<script setup>
import { computed, onMounted, ref } from 'vue'
import http from '@/api/http'
import CrudPage from '@/components/CrudPage.vue'
import { fmtDateTime } from '@/utils/format'

const roles = ref([])
onMounted(async () => { roles.value = (await http.get('/roles')).data.items })

const config = computed(() => ({
  title: 'អ្នកប្រើប្រាស់', endpoint: '/users', module: 'users', formWidth: '640px',
  canDelete: (r) => r.active,
  columns: [
    { key: 'username', label: 'ឈ្មោះអ្នកប្រើ', width: 150 },
    { key: 'full_name', label: 'ឈ្មោះពេញ', minWidth: 160 },
    { key: 'phone', label: 'ទូរសព្ទ', width: 130 },
    { key: 'role_name', label: 'តួនាទី', width: 200 },
    { key: 'unit_scope_name', label: 'ដែនសិទ្ធិអង្គភាព', minWidth: 160, value: (r) => r.unit_scope_name || 'គ្រប់អង្គភាព' },
    { key: 'last_login_at', label: 'ចូលចុងក្រោយ', width: 150, value: (r) => fmtDateTime(r.last_login_at) },
    { key: 'active', label: 'ស្ថានភាព', width: 100, value: (r) => (r.active ? 'សកម្ម' : 'បានបិទ'), tag: (r) => (r.active ? 'success' : 'info') },
  ],
  fields: [
    { key: 'username', label: 'ឈ្មោះអ្នកប្រើ', required: true, span: 12 },
    { key: 'full_name', label: 'ឈ្មោះពេញ', required: true, span: 12 },
    { key: 'phone', label: 'ទូរសព្ទ', span: 12 },
    { key: 'role_id', label: 'តួនាទី', type: 'select', required: true, span: 12, options: roles.value.map((r) => ({ value: r.id, label: r.description || r.name })) },
    { key: 'unit_scope_id', label: 'ដែនសិទ្ធិអង្គភាព (ទុកទំនេរ = គ្រប់អង្គភាព)', type: 'unit' },
    { key: 'password', label: 'ពាក្យសម្ងាត់ (យ៉ាងតិច ៨ តួ; ទុកទំនេរ = មិនប្ដូរ)', span: 16 },
    { key: 'active', label: 'សកម្ម', type: 'switch', default: true, span: 8 },
  ],
}))
</script>

<template>
  <CrudPage :config="config" />
</template>
