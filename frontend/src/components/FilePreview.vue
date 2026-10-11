<script setup>
/**
 * Full-screen preview for attachments.
 * items: [{ name, size?, url? (ready object URL, e.g. a file not uploaded yet), fetchUrl? (protected API path) }]
 * v-model = index of the open item (null = closed)
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { blobUrl } from '@/api/http'
import { fileKind, KIND_COLOR, KIND_ICON } from '@/utils/files'
import { fileSize } from '@/utils/format'

const props = defineProps({
  items: { type: Array, default: () => [] },
  modelValue: { type: Number, default: null },
})
const emit = defineEmits(['update:modelValue'])

const cache = new Map() // fetchUrl -> object URL
const src = ref('')
const loading = ref(false)
const failed = ref(false)
const zoom = ref(1)
const rotate = ref(0)

const open = computed(() => props.modelValue !== null && props.modelValue !== undefined && !!props.items[props.modelValue])
const item = computed(() => (open.value ? props.items[props.modelValue] : null))
const kind = computed(() => fileKind(item.value?.name))
const canPreview = computed(() => ['image', 'pdf'].includes(kind.value))

async function load() {
  src.value = ''
  failed.value = false
  zoom.value = 1
  rotate.value = 0
  const it = item.value
  if (!it) return
  if (it.url) { src.value = it.url; return }
  if (!it.fetchUrl) return
  if (cache.has(it.fetchUrl)) { src.value = cache.get(it.fetchUrl); return }
  loading.value = true
  try {
    const u = await blobUrl(it.fetchUrl)
    cache.set(it.fetchUrl, u)
    if (item.value === it) src.value = u
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

watch(item, load, { immediate: true })

function close() { emit('update:modelValue', null) }
function go(step) {
  const n = props.items.length
  if (n) emit('update:modelValue', (props.modelValue + step + n) % n)
}

async function downloadIt() {
  if (!src.value) await load()
  const a = document.createElement('a')
  a.href = src.value
  a.download = item.value.name
  a.click()
}
function newTab() { if (src.value) window.open(src.value, '_blank') }

function onKey(e) {
  if (!open.value) return
  if (e.key === 'ArrowRight') go(1)
  if (e.key === 'ArrowLeft') go(-1)
}
window.addEventListener('keydown', onKey)
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  cache.forEach((u) => URL.revokeObjectURL(u))
})
</script>

<template>
  <el-dialog :model-value="open" width="min(1100px, 96vw)" top="3vh" append-to-body destroy-on-close class="file-preview"
             @close="close">
    <template #header>
      <div v-if="item" class="pv-head">
        <el-icon :size="20" :color="KIND_COLOR[kind]"><component :is="KIND_ICON[kind]" /></el-icon>
        <span class="pv-name" :title="item.name">{{ item.name }}</span>
        <span class="muted">{{ fileSize(item.size) }}</span>
        <span v-if="items.length > 1" class="muted">· {{ modelValue + 1 }} / {{ items.length }}</span>
      </div>
    </template>

    <div v-if="item" v-loading="loading" class="pv-body">
      <template v-if="canPreview && src">
        <div v-if="kind === 'image'" class="pv-image">
          <img :src="src" :alt="item.name" :style="{ transform: `scale(${zoom}) rotate(${rotate}deg)` }" />
        </div>
        <iframe v-else :src="src" class="pv-pdf" title="PDF" />
      </template>
      <el-result v-else-if="!loading" icon="info" :title="failed ? 'មិនអាចបើកឯកសារនេះបានទេ' : 'មិនអាចមើលជាមុនបាន'"
                 sub-title="ប្រភេទឯកសារនេះ (Word / Excel) ត្រូវទាញយកមកបើកលើកុំព្យូទ័រ">
        <template #icon><el-icon :size="64" :color="KIND_COLOR[kind]"><component :is="KIND_ICON[kind]" /></el-icon></template>
        <template #extra><el-button type="primary" icon="Download" @click="downloadIt">ទាញយក</el-button></template>
      </el-result>

      <el-button v-if="items.length > 1" class="pv-nav prev" circle icon="ArrowLeftBold" @click="go(-1)" />
      <el-button v-if="items.length > 1" class="pv-nav next" circle icon="ArrowRightBold" @click="go(1)" />
    </div>

    <template #footer>
      <div class="pv-foot">
        <span v-if="kind === 'image'">
          <el-button icon="ZoomOut" @click="zoom = Math.max(0.2, zoom - 0.2)" />
          <el-button @click="zoom = 1; rotate = 0">{{ Math.round(zoom * 100) }}%</el-button>
          <el-button icon="ZoomIn" @click="zoom = Math.min(5, zoom + 0.2)" />
          <el-button icon="RefreshRight" @click="rotate += 90" />
        </span>
        <span v-else />
        <span>
          <el-button v-if="canPreview" icon="TopRight" @click="newTab">បើកផ្ទាំងថ្មី</el-button>
          <el-button type="primary" icon="Download" @click="downloadIt">ទាញយក</el-button>
        </span>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.pv-head { display: flex; align-items: center; gap: 8px; min-width: 0; padding-right: 30px; }
.pv-name { font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pv-body { position: relative; height: 76vh; background: #2b2f33; border-radius: 6px; display: flex; align-items: center; justify-content: center; overflow: hidden; }
.pv-body :deep(.el-result) { background: #fff; border-radius: 8px; padding: 30px 50px; }
.pv-image { width: 100%; height: 100%; overflow: auto; display: flex; align-items: center; justify-content: center; }
.pv-image img { max-width: 100%; max-height: 100%; transition: transform 0.15s; transform-origin: center; }
.pv-pdf { width: 100%; height: 100%; border: 0; background: #fff; }
.pv-nav { position: absolute; top: 50%; transform: translateY(-50%); opacity: 0.85; }
.pv-nav.prev { left: 12px; }
.pv-nav.next { right: 12px; }
.pv-foot { display: flex; justify-content: space-between; align-items: center; }
</style>
