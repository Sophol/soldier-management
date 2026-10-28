<script setup>
/**
 * Saved filters (រក្សា Filter ទុកប្រើឡើងវិញ) of one list: apply, save the current filter under a name
 * (optionally shared with the other users), delete.
 * props.current(): the filter values in use; emits apply(params) with a saved filter's values.
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '@/api/http'

const props = defineProps({ module: { type: String, required: true }, current: { type: Function, required: true } })
const emit = defineEmits(['apply'])

const items = ref([])
const dialog = ref(false)
const form = reactive({ name: '', shared: false })

async function load() {
  items.value = (await http.get('/saved-filters', { params: { module: props.module }, silent: true })).data
}

function openSave() {
  form.name = ''
  form.shared = false
  dialog.value = true
}

async function save() {
  if (!form.name.trim()) return ElMessage.warning('សូមដាក់ឈ្មោះ Filter')
  await http.post('/saved-filters', { module: props.module, name: form.name.trim(), shared: form.shared, params: props.current() })
  ElMessage.success('បានរក្សាទុក Filter')
  dialog.value = false
  load()
}

async function remove(f) {
  await ElMessageBox.confirm(`លុប Filter "${f.name}"?`, 'បញ្ជាក់', { type: 'warning', confirmButtonText: 'លុប', cancelButtonText: 'បោះបង់' })
  await http.delete(`/saved-filters/${f.id}`)
  load()
}

onMounted(() => load().catch(() => {}))
</script>

<template>
  <el-dropdown trigger="click" @command="(f) => emit('apply', { ...f.params })">
    <el-button icon="Star">Filter ដែលបានរក្សាទុក <span v-if="items.length" class="count">({{ items.length }})</span></el-button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item v-for="f in items" :key="f.id" :command="f">
          <div class="item">
            <span>{{ f.name }}</span>
            <el-tag v-if="!f.mine" size="small" type="info">{{ f.owner }}</el-tag>
            <el-tag v-else-if="f.shared" size="small">ចែករំលែក</el-tag>
            <el-button v-if="f.mine" link type="danger" icon="Delete" @click.stop="remove(f)" />
          </div>
        </el-dropdown-item>
        <el-dropdown-item v-if="!items.length" disabled>មិនទាន់មាន Filter ដែលបានរក្សាទុក</el-dropdown-item>
        <el-dropdown-item divided icon="Plus" @click="openSave">រក្សាទុក Filter បច្ចុប្បន្ន...</el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>

  <el-dialog v-model="dialog" title="រក្សាទុក Filter" width="420px" append-to-body>
    <el-form label-position="top" @submit.prevent="save">
      <el-form-item label="ឈ្មោះ Filter (ឈ្មោះដដែល = ជំនួស Filter ចាស់)">
        <el-input v-model="form.name" maxlength="150" placeholder="ឧ. នាយទាហានជិតនិវត្តក្នុង ២ ឆ្នាំ" autofocus />
      </el-form-item>
      <el-checkbox v-model="form.shared">ចែករំលែកឲ្យអ្នកប្រើប្រាស់ផ្សេងទៀតប្រើបាន</el-checkbox>
    </el-form>
    <template #footer>
      <el-button @click="dialog = false">បោះបង់</el-button>
      <el-button type="primary" @click="save">រក្សាទុក</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.count { margin-left: 2px; }
.item { display: flex; align-items: center; gap: 8px; min-width: 220px; }
.item > span { flex: 1; }
</style>
