<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '@/api/http'
import { useAuth } from '@/stores/auth'

const auth = useAuth()
const form = reactive({ old_password: '', new_password: '', confirm: '' })
const formRef = ref()
const saving = ref(false)
const rules = {
  old_password: [{ required: true, message: 'សូមបញ្ចូលពាក្យសម្ងាត់ចាស់' }],
  new_password: [{ required: true, min: 8, message: 'យ៉ាងតិច ៨ តួអក្សរ' }],
  confirm: [{ validator: (_, v, cb) => (v === form.new_password ? cb() : cb(new Error('ពាក្យសម្ងាត់មិនដូចគ្នា'))) }],
}

async function submit() {
  await formRef.value.validate()
  saving.value = true
  try {
    await http.post('/auth/change-password', { old_password: form.old_password, new_password: form.new_password })
    ElMessage.success('បានប្ដូរពាក្យសម្ងាត់')
    Object.assign(form, { old_password: '', new_password: '', confirm: '' })
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="page">
    <div class="page-head"><h2>ព័ត៌មានគណនី</h2></div>
    <el-row :gutter="14">
      <el-col :xs="24" :md="10">
        <el-card shadow="never" header="គណនី">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="ឈ្មោះអ្នកប្រើ">{{ auth.user.username }}</el-descriptions-item>
            <el-descriptions-item label="ឈ្មោះពេញ">{{ auth.user.full_name }}</el-descriptions-item>
            <el-descriptions-item label="តួនាទី">{{ auth.user.role_name }}</el-descriptions-item>
            <el-descriptions-item label="ដែនសិទ្ធិអង្គភាព">{{ auth.user.unit_scope_name || 'គ្រប់អង្គភាព' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="10">
        <el-card shadow="never" header="ប្ដូរពាក្យសម្ងាត់">
          <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="submit">
            <el-form-item label="ពាក្យសម្ងាត់ចាស់" prop="old_password"><el-input v-model="form.old_password" type="password" show-password /></el-form-item>
            <el-form-item label="ពាក្យសម្ងាត់ថ្មី" prop="new_password"><el-input v-model="form.new_password" type="password" show-password /></el-form-item>
            <el-form-item label="បញ្ជាក់ពាក្យសម្ងាត់ថ្មី" prop="confirm"><el-input v-model="form.confirm" type="password" show-password /></el-form-item>
            <el-button type="primary" native-type="submit" :loading="saving">រក្សាទុក</el-button>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>
