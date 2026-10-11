<script setup>
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '@/api/http'
import { useAuth } from '@/stores/auth'
import { useLookups } from '@/stores/lookups'
import UnitTreeSelect from '@/components/UnitTreeSelect.vue'
import { num } from '@/utils/format'

const auth = useAuth()
const lookups = useLookups()
const filter = ref('')
const treeRef = ref()
const dialog = ref(false)
const form = ref({})
const formRef = ref()
const saving = ref(false)
const LEVEL_TAG = { 1: 'danger', 2: 'warning', 3: 'success', 4: 'info' }

const tree = computed(() => lookups.unitTree)
const rules = { name_kh: [{ required: true, message: 'សូមបញ្ចូលឈ្មោះ' }] }

function filterNode(value, data) {
  return !value || data.name_kh.includes(value) || (data.name_en || '').toLowerCase().includes(value.toLowerCase())
    || (data.code || '').includes(value)
}

function openCreate(parent = null) {
  form.value = { parent_id: parent?.id ?? null, name_kh: '', name_en: '', code: '', sort_order: 0, active: true, level: 1 }
  dialog.value = true
}

function openEdit(node) {
  const { id, parent_id, name_kh, name_en, code, sort_order, active, level } = node
  form.value = { id, parent_id, name_kh, name_en, code, sort_order, active, level }
  dialog.value = true
}

async function save() {
  await formRef.value.validate()
  saving.value = true
  try {
    const { id, ...payload } = form.value
    if (id) await http.put(`/units/${id}`, payload)
    else await http.post('/units', payload)
    ElMessage.success('បានរក្សាទុក')
    dialog.value = false
    await lookups.refresh()
  } finally {
    saving.value = false
  }
}

async function remove(node) {
  await ElMessageBox.confirm(`លុប "${node.name_kh}"?`, 'បញ្ជាក់', { type: 'warning' })
  await http.delete(`/units/${node.id}`)
  ElMessage.success('បានលុប')
  await lookups.refresh()
}

function sumCount(n) {
  return n.soldier_count + (n.children || []).reduce((s, c) => s + sumCount(c), 0)
}
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h2>ស្ថាប័នកងឯកភាព</h2>
      <div class="head-actions">
        <el-input v-model="filter" placeholder="ស្វែងរកអង្គភាព..." prefix-icon="Search" clearable style="width: 240px"
                  @input="treeRef.filter(filter)" />
        <el-button v-if="auth.can('org_units.create')" type="primary" icon="Plus" @click="openCreate()">បន្ថែមស្ថាប័នកងឯកភាព</el-button>
      </div>
    </div>
    <el-alert type="info" :closable="false" show-icon
              title="រចនាសម្ព័ន្ធ៖ ស្ថាប័នកងឯកភាព → អង្គភាព → អង្គភាពរង → អង្គភាពចំណុះផ្ទាល់ (ចុច + ដើម្បីបន្ថែមអង្គភាពក្រោម)" />
    <el-card shadow="never">
      <el-empty v-if="!tree.length" description="មិនទាន់មានអង្គភាព" />
      <el-tree ref="treeRef" :data="tree" node-key="id" default-expand-all :expand-on-click-node="false"
               :filter-node-method="filterNode" :props="{ label: 'name_kh', children: 'children' }">
        <template #default="{ data }">
          <div class="node">
            <el-tag :type="LEVEL_TAG[data.level]" size="small">{{ data.level_name }}</el-tag>
            <span :class="{ inactive: !data.active }">{{ data.name_kh }}</span>
            <span v-if="data.code" class="muted">({{ data.code }})</span>
            <el-tag size="small" effect="plain" round>{{ num(sumCount(data)) }} នាក់</el-tag>
            <span class="node-actions">
              <el-button v-if="auth.can('org_units.create') && data.level < 4" link type="success" icon="Plus" @click.stop="openCreate(data)" />
              <el-button v-if="auth.can('org_units.update')" link type="primary" icon="Edit" @click.stop="openEdit(data)" />
              <el-button v-if="auth.can('org_units.delete')" link type="danger" icon="Delete" @click.stop="remove(data)" />
            </span>
          </div>
        </template>
      </el-tree>
    </el-card>

    <el-dialog v-model="dialog" :title="form.id ? 'កែប្រែអង្គភាព' : 'បន្ថែមអង្គភាព'" width="560px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="ស្ថិតក្រោម (ទុកទំនេរ = ស្ថាប័នកងឯកភាព)">
          <UnitTreeSelect v-model="form.parent_id" :max-level="3" :exclude-id="form.id" />
        </el-form-item>
        <el-form-item label="ឈ្មោះ (ខ្មែរ)" prop="name_kh"><el-input v-model="form.name_kh" /></el-form-item>
        <el-form-item label="ឈ្មោះ (អង់គ្លេស)"><el-input v-model="form.name_en" /></el-form-item>
        <el-row :gutter="12">
          <el-col :span="10"><el-form-item label="កូដ"><el-input v-model="form.code" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="លំដាប់"><el-input-number v-model="form.sort_order" :min="0" style="width: 100%" /></el-form-item></el-col>
          <el-col :span="6"><el-form-item label="សកម្ម"><el-switch v-model="form.active" /></el-form-item></el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">បោះបង់</el-button>
        <el-button type="primary" :loading="saving" @click="save">រក្សាទុក</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.node { display: flex; align-items: center; gap: 8px; flex: 1; padding-right: 8px; }
.node-actions { margin-left: auto; }
.inactive { text-decoration: line-through; color: var(--muted); }
:deep(.el-tree-node__content) { height: 36px; }
</style>
