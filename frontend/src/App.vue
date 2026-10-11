<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import km from 'element-plus/es/locale/lang/km'
import en from 'element-plus/es/locale/lang/en'

// Element Plus built-in texts (select placeholder, pagination, date picker...) follow the app language
const { locale } = useI18n()
const elLocale = computed(() => (locale.value === 'en' ? en : km))
</script>

<template>
  <el-config-provider :locale="elLocale">
    <router-view />
  </el-config-provider>
</template>
