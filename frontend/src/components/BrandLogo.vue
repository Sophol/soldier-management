<script setup>
/** The organisation's logo (uploaded under ការកំណត់ប្រព័ន្ធ); the built-in icon when none is uploaded. */
import { ref, watch } from 'vue'
import { logoVersion } from '@/utils/logo'

const src = ref('')
const fallback = '/favicon.svg'
watch(logoVersion, (v) => { src.value = `/api/v1/settings/logo?v=${v}` }, { immediate: true })
</script>

<template>
  <img :src="src" alt="" @error="src = fallback" />
</template>
