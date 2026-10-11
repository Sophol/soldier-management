<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuth } from '@/stores/auth'
import { menu } from '@/menu'
import { setLocale } from '@/i18n'
import { prefs } from '@/utils/format'

const { t, locale } = useI18n()
const auth = useAuth()
const route = useRoute()
const router = useRouter()
const collapsed = ref(false)
const khmerDigits = ref(prefs.khmerDigits)

const items = computed(() => menu
  .map((m) => (m.children ? { ...m, children: m.children.filter((c) => auth.can(c.perm)) } : m))
  .filter((m) => (m.children ? m.children.length : auth.can(m.perm))))

const active = computed(() => {
  const all = menu.flatMap((m) => (m.children ? m.children : [m]))
  const match = all.filter((m) => route.path === m.to || (m.to !== '/' && route.path.startsWith(`${m.to}/`)))
  return match.sort((a, b) => b.to.length - a.to.length)[0]?.to || route.path
})

function toggleDigits(v) {
  prefs.khmerDigits = v
  window.location.reload()
}

function onCommand(cmd) {
  if (cmd === 'logout') auth.logout()
  if (cmd === 'account') router.push('/account')
}
</script>

<template>
  <el-container class="layout">
    <el-aside :width="collapsed ? '64px' : '270px'" class="app-aside">
      <div class="brand" @click="router.push('/')">
        <img src="/favicon.svg" alt="" />
        <div v-if="!collapsed" class="brand-text">
          <div class="moul">{{ t('app.title') }}</div>
          <small>{{ t('app.subtitle') }}</small>
        </div>
      </div>
      <el-scrollbar>
        <el-menu :default-active="active" :collapse="collapsed" router background-color="#173d30"
                 text-color="#d6e2dc" active-text-color="#f2d16b" unique-opened>
          <template v-for="m in items" :key="m.key">
            <el-sub-menu v-if="m.children" :index="m.key">
              <template #title>
                <el-icon><component :is="m.icon" /></el-icon>
                <span>{{ t(`menu.${m.key}`) }}</span>
              </template>
              <el-menu-item v-for="c in m.children" :key="c.to" :index="c.to">{{ t(`menu.${c.key}`) }}</el-menu-item>
            </el-sub-menu>
            <el-menu-item v-else :index="m.to">
              <el-icon><component :is="m.icon" /></el-icon>
              <template #title>{{ t(`menu.${m.key}`) }}</template>
            </el-menu-item>
          </template>
        </el-menu>
      </el-scrollbar>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <el-button text :icon="collapsed ? 'Expand' : 'Fold'" @click="collapsed = !collapsed" />
        <div class="spacer" />
        <el-switch v-model="khmerDigits" :active-text="t('common.khmerDigits')" @change="toggleDigits" />
        <el-select :model-value="locale" style="width: 110px" @change="setLocale">
          <el-option value="km" label="ខ្មែរ" />
          <el-option value="en" label="English" />
        </el-select>
        <el-dropdown @command="onCommand">
          <span class="user">
            <el-avatar :size="30" icon="UserFilled" />
            <span>{{ auth.user?.full_name }}</span>
            <el-tag size="small" type="warning">{{ auth.user?.role_name }}</el-tag>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="account" icon="Key">{{ t('common.changePassword') }}</el-dropdown-item>
              <el-dropdown-item command="logout" icon="SwitchButton" divided>{{ t('common.logout') }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main class="main">
        <router-view :key="route.path" />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout { height: 100vh; }
.app-aside { background: #173d30; display: flex; flex-direction: column; transition: width 0.2s; overflow: hidden; }
.brand { display: flex; gap: 10px; align-items: center; padding: 14px 12px; color: #fff; cursor: pointer; border-bottom: 1px solid rgba(255, 255, 255, 0.08); }
.brand img { width: 38px; height: 38px; flex-shrink: 0; }
.brand-text .moul { font-size: 13px; line-height: 1.7; color: #f2d16b; }
.brand-text small { display: block; font-size: 11px; color: #b7c9c0; line-height: 1.5; }
.el-menu { border-right: none; }
.app-header { display: flex; align-items: center; gap: 14px; background: #fff; border-bottom: 1px solid #e4e8eb; height: 56px; }
.spacer { flex: 1; }
.user { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.main { padding: 0; background: var(--bg); }
</style>
