<script setup>
/** One attachment card: image thumbnail or file-type icon, name and size. */
import { onBeforeUnmount, ref, watch } from 'vue'
import { blobUrl } from '@/api/http'
import { fileKind, KIND_COLOR, KIND_ICON } from '@/utils/files'
import { fileSize } from '@/utils/format'

const props = defineProps({
  name: { type: String, required: true },
  size: { type: Number, default: 0 },
  url: { type: String, default: '' }, // ready object URL (local file)
  fetchUrl: { type: String, default: '' }, // protected API path
  removable: { type: Boolean, default: false },
})
defineEmits(['open', 'remove', 'download'])

const kind = fileKind(props.name)
const thumb = ref('')
let owned = ''

watch(() => [props.url, props.fetchUrl], async () => {
  if (kind !== 'image') return
  if (props.url) { thumb.value = props.url; return }
  if (props.fetchUrl) {
    try { owned = await blobUrl(props.fetchUrl); thumb.value = owned } catch { thumb.value = '' }
  }
}, { immediate: true })
onBeforeUnmount(() => owned && URL.revokeObjectURL(owned))
</script>

<template>
  <div class="thumb" :title="name">
    <div class="thumb-media" @click="$emit('open')">
      <img v-if="thumb" :src="thumb" :alt="name" />
      <el-icon v-else :size="42" :color="KIND_COLOR[kind]"><component :is="KIND_ICON[kind]" /></el-icon>
      <span class="badge" :style="{ background: KIND_COLOR[kind] }">{{ name.split('.').pop().toUpperCase() }}</span>
      <div class="hover"><el-icon :size="22"><View /></el-icon></div>
    </div>
    <div class="thumb-info">
      <div class="thumb-name">{{ name }}</div>
      <div class="thumb-meta">
        <span class="muted">{{ fileSize(size) }}</span>
        <span>
          <el-button link icon="Download" @click="$emit('download')" />
          <el-button v-if="removable" link type="danger" icon="Delete" @click="$emit('remove')" />
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.thumb { width: 150px; border: 1px solid #e2e7eb; border-radius: 8px; overflow: hidden; background: #fff; }
.thumb-media { position: relative; height: 110px; display: flex; align-items: center; justify-content: center; background: #f4f6f8; cursor: zoom-in; }
.thumb-media img { width: 100%; height: 100%; object-fit: cover; }
.badge { position: absolute; left: 6px; top: 6px; color: #fff; font-size: 10px; font-weight: 700; padding: 0 6px; border-radius: 4px; line-height: 18px; }
.hover { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; background: rgba(0, 0, 0, 0.35); color: #fff; opacity: 0; transition: opacity 0.15s; }
.thumb-media:hover .hover { opacity: 1; }
.thumb-info { padding: 6px 8px; }
.thumb-name { font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.6; }
.thumb-meta { display: flex; justify-content: space-between; align-items: center; font-size: 11px; }
</style>
