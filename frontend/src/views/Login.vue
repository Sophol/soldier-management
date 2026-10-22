<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuth } from '@/stores/auth'
import BrandLogo from '@/components/BrandLogo.vue'

const { t } = useI18n()
const auth = useAuth()
const router = useRouter()
const route = useRoute()
const form = reactive({ username: '', password: '' })
const loading = ref(false)

async function submit() {
  if (!form.username || !form.password) return
  loading.value = true
  try {
    await auth.login(form.username, form.password)
    router.replace(route.query.next || '/')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <div class="login-card">
      <BrandLogo class="logo" />
      <div class="moul kingdom">ព្រះរាជាណាចក្រកម្ពុជា</div>
      <div class="moul motto">ជាតិ សាសនា ព្រះមហាក្សត្រ</div>
      <h1 class="moul">{{ t('app.title') }}</h1>
      <p class="muted">{{ t('app.subtitle') }}</p>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item :label="t('login.username')">
          <el-input v-model="form.username" size="large" prefix-icon="User" autofocus autocomplete="username" />
        </el-form-item>
        <el-form-item :label="t('login.password')">
          <el-input v-model="form.password" size="large" type="password" prefix-icon="Lock" show-password
                    autocomplete="current-password" />
        </el-form-item>
        <el-button type="primary" size="large" native-type="submit" :loading="loading" style="width: 100%">
          {{ t('login.submit') }}
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.login-wrap { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 16px;
  background: linear-gradient(135deg, #173d30 0%, #24614b 60%, #3c7a62 100%); }
.login-card { width: 100%; max-width: 420px; background: #fff; border-radius: 12px; padding: 32px 30px; text-align: center;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.25); }
.logo { width: 64px; height: 64px; object-fit: contain; }
.kingdom { font-size: 15px; margin-top: 8px; color: #173d30; }
.motto { font-size: 13px; color: #173d30; }
h1 { font-size: 18px; color: #24614b; margin: 18px 0 4px; line-height: 1.8; }
.el-form { text-align: left; margin-top: 18px; }
</style>
