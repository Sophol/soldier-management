<script setup>
/**
 * Attachments of a saved record: drag & drop / multi-file upload, thumbnail grid, click to preview.
 * ownerType: doc_in | doc_out | decision | training | ... ; soldier attachments pass their own baseUrl.
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http, { download } from '@/api/http'
import { ACCEPT } from '@/utils/files'
import FilePreview from './FilePreview.vue'
import FileThumb from './FileThumb.vue'

const props = defineProps({
  ownerType: { type: String, required: true },
  ownerId: { type: Number, required: true },
  editable: { type: Boolean, default: true },
  baseUrl: { type: String, default: '' },
})
const emit = defineEmits(['changed'])
const files = ref([])
const loading = ref(false)
const uploading = ref(0)
const previewIndex = ref(null)

const listUrl = () => props.baseUrl || `/files/${props.ownerType}/${props.ownerId}`
const fileUrl = (f) => (props.baseUrl ? `${props.baseUrl}/${f.id}` : `/files/download/${f.id}?inline=1`)
const deleteUrl = (f) => (props.baseUrl ? `${props.baseUrl}/${f.id}` : `/files/${f.id}`)
const items = computed(() => files.value.map((f) => ({ name: f.file_name, size: f.file_size, fetchUrl: fileUrl(f) })))

async function load() {
  loading.value = true
  try {
    files.value = (await http.get(listUrl())).data
  } finally {
    loading.value = false
  }
}

async function upload({ file }) {
  const form = new FormData()
  form.append('file', file)
  uploading.value++
  try {
    await http.post(listUrl(), form)
    await load()
    emit('changed', files.value.length)
  } finally {
    uploading.value--
  }
}

async function remove(f) {
  await ElMessageBox.confirm(`លុបឯកសារ "${f.file_name}"?`, 'បញ្ជាក់', { type: 'warning', confirmButtonText: 'លុប', cancelButtonText: 'បោះបង់' })
  await http.delete(deleteUrl(f))
  ElMessage.success('បានលុប')
  await load()
  emit('changed', files.value.length)
}

onMounted(load)
defineExpose({ load })
</script>

<template>
  <div v-loading="loading">
    <el-upload v-if="editable" drag multiple :show-file-list="false" :http-request="upload" :accept="ACCEPT" class="drop">
      <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
      <div class="el-upload__text">
        អូសឯកសារមកទីនេះ ឬ <em>ចុចដើម្បីជ្រើសរើស</em>
        <div class="muted small">PDF, រូបភាព (JPG, PNG), Word, Excel · អាចជ្រើសច្រើនឯកសារក្នុងពេលតែមួយ</div>
      </div>
    </el-upload>
    <div v-if="uploading" class="muted small uploading"><el-icon class="is-loading"><Loading /></el-icon> កំពុងផ្ទុក {{ uploading }} ឯកសារ...</div>

    <div v-if="files.length" class="grid">
      <FileThumb v-for="(f, i) in files" :key="f.id" :name="f.file_name" :size="f.file_size" :fetch-url="fileUrl(f)"
                 :removable="editable" @open="previewIndex = i" @remove="remove(f)"
                 @download="download(fileUrl(f).replace('?inline=1', ''), {}, f.file_name)" />
    </div>
    <el-empty v-else-if="!loading && !editable" description="គ្មានឯកសារភ្ជាប់" :image-size="60" />

    <FilePreview v-model="previewIndex" :items="items" />
  </div>
</template>

<style scoped>
.drop :deep(.el-upload-dragger) { padding: 16px; }
.drop :deep(.el-icon--upload) { font-size: 40px; margin-bottom: 4px; }
.grid { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 12px; }
.small { font-size: 12px; }
.uploading { margin-top: 6px; display: flex; gap: 6px; align-items: center; }
</style>
