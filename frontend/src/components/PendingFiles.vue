<script setup>
/** Files chosen for a record that is not saved yet; v-model is an array of File objects. */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ACCEPT } from '@/utils/files'
import FilePreview from './FilePreview.vue'
import FileThumb from './FileThumb.vue'

const props = defineProps({ modelValue: { type: Array, default: () => [] }, maxMb: { type: Number, default: 20 } })
const emit = defineEmits(['update:modelValue'])
const previewIndex = ref(null)
const urls = new Map() // File -> object URL
let local = [...props.modelValue]

const urlOf = (f) => {
  if (!urls.has(f)) urls.set(f, URL.createObjectURL(f))
  return urls.get(f)
}
const items = computed(() => props.modelValue.map((f) => ({ name: f.name, size: f.size, url: urlOf(f) })))

function add(uploadFile) {
  const f = uploadFile.raw
  if (f.size > props.maxMb * 1024 * 1024) {
    ElMessage.warning(`${f.name}: ធំពេក (អតិបរមា ${props.maxMb}MB)`)
    return
  }
  // several files arrive in the same tick: build on a local list, not the (not yet updated) prop
  if (local.some((x) => x.name === f.name && x.size === f.size)) return
  local = [...local, f]
  emit('update:modelValue', local)
}

function remove(i) {
  const list = [...local]
  const [f] = list.splice(i, 1)
  if (urls.has(f)) { URL.revokeObjectURL(urls.get(f)); urls.delete(f) }
  local = list
  emit('update:modelValue', list)
}

function save(f) {
  const a = document.createElement('a')
  a.href = urlOf(f)
  a.download = f.name
  a.click()
}

watch(() => props.modelValue, (v) => { local = [...v] })
watch(() => props.modelValue.length, (n) => { if (!n) { urls.forEach((u) => URL.revokeObjectURL(u)); urls.clear() } })
onBeforeUnmount(() => urls.forEach((u) => URL.revokeObjectURL(u)))
</script>

<template>
  <div>
    <el-upload drag multiple :auto-upload="false" :show-file-list="false" :accept="ACCEPT" :on-change="add" class="drop">
      <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
      <div class="el-upload__text">
        អូសឯកសារមកទីនេះ ឬ <em>ចុចដើម្បីជ្រើសរើស</em>
        <div class="muted small">ឯកសារនឹងត្រូវផ្ទុកឡើង ពេលចុច "រក្សាទុក"</div>
      </div>
    </el-upload>
    <div v-if="modelValue.length" class="grid">
      <FileThumb v-for="(f, i) in modelValue" :key="f.name + f.size" :name="f.name" :size="f.size" :url="urlOf(f)"
                 removable @open="previewIndex = i" @remove="remove(i)" @download="save(f)" />
    </div>
    <FilePreview v-model="previewIndex" :items="items" />
  </div>
</template>

<style scoped>
.drop :deep(.el-upload-dragger) { padding: 16px; }
.drop :deep(.el-icon--upload) { font-size: 40px; margin-bottom: 4px; }
.grid { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 12px; }
.small { font-size: 12px; }
</style>
