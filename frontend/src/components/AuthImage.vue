<script setup>
/** <img> for files that need the Bearer token (soldier photos). */
import { onBeforeUnmount, ref, watch } from 'vue'
import { blobUrl } from '@/api/http'

const props = defineProps({ src: { type: String, default: '' }, alt: { type: String, default: '' } })
const url = ref('')

watch(() => props.src, async (src) => {
  if (url.value) URL.revokeObjectURL(url.value)
  url.value = ''
  if (src) {
    try { url.value = await blobUrl(src) } catch { url.value = '' }
  }
}, { immediate: true })

onBeforeUnmount(() => url.value && URL.revokeObjectURL(url.value))
</script>

<template>
  <img v-if="url" :src="url" :alt="alt" />
  <div v-else class="photo-placeholder"><el-icon :size="40"><UserFilled /></el-icon></div>
</template>

<style scoped>
.photo-placeholder { display: flex; align-items: center; justify-content: center; background: #eef1f4; color: #9aa4ae; width: 100%; height: 100%; }
</style>
