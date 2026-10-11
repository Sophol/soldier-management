<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '@/api/http'
import { useAuth } from '@/stores/auth'

const auth = useAuth()
const items = ref([])
const saving = ref(false)
const LABELS = {
  org_name_kh: 'ឈ្មោះស្ថាប័ន (ខ្មែរ) — បង្ហាញលើឯកសារបោះពុម្ព',
  org_name_en: 'ឈ្មោះស្ថាប័ន (អង់គ្លេស)',
  outgoing_number_format: 'ទម្រង់លេខឯកសារចេញ ({seq} = លេខរៀង, {yy} = ឆ្នាំ ២ខ្ទង់, {yyyy} = ឆ្នាំ ៤ខ្ទង់)',
  retirement_age_male: 'អាយុចូលនិវត្តន៍ — ប្រុស',
  retirement_age_female: 'អាយុចូលនិវត្តន៍ — ស្រី',
  alert_months_ahead: 'ជូនដំណឹងនិវត្តន៍មុន (ខែ)',
}

onMounted(async () => {
  const { data } = await http.get('/settings')
  items.value = Object.entries(data).map(([key, v]) => ({ key, value: v.value, description: v.description }))
})

async function save() {
  saving.value = true
  try {
    await http.put('/settings', { values: Object.fromEntries(items.value.map((i) => [i.key, i.value])) })
    ElMessage.success('បានរក្សាទុក')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h2>ការកំណត់ប្រព័ន្ធ</h2>
      <el-button v-if="auth.can('settings.update')" type="primary" icon="Check" :loading="saving" @click="save">រក្សាទុក</el-button>
    </div>
    <el-card shadow="never">
      <el-form label-position="top" style="max-width: 720px">
        <el-form-item v-for="i in items" :key="i.key" :label="LABELS[i.key] || i.description || i.key">
          <el-input v-model="i.value" :disabled="!auth.can('settings.update')" />
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>
