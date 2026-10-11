<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '@/api/http'
import { useAuth } from '@/stores/auth'

const auth = useAuth()
const roles = ref([])
const catalog = ref({ modules: [], actions: [] })
const selected = ref(null)
const checked = ref(new Set())
const saving = ref(false)
const ACTION_LABEL = { view: 'មើល', create: 'បង្កើត', update: 'កែប្រែ', delete: 'លុប', search: 'ស្វែងរក', print: 'បោះពុម្ព', export: 'នាំចេញ', approve: 'អនុម័ត' }

const role = computed(() => roles.value.find((r) => r.id === selected.value))
const editable = computed(() => role.value && !role.value.is_super && auth.can('roles.update'))

async function load() {
  const [r, c] = await Promise.all([http.get('/roles'), http.get('/permissions/catalog')])
  roles.value = r.data.items
  catalog.value = c.data
  if (!selected.value && roles.value.length) select(roles.value[0].id)
  else if (selected.value) select(selected.value)
}

function select(id) {
  selected.value = id
  checked.value = new Set(roles.value.find((r) => r.id === id)?.permissions || [])
}

const has = (m, a) => role.value?.is_super || checked.value.has(`${m}.${a}`)
function toggle(m, a, v) {
  const s = new Set(checked.value)
  v ? s.add(`${m}.${a}`) : s.delete(`${m}.${a}`)
  checked.value = s
}
function toggleRow(m, v) {
  const s = new Set(checked.value)
  catalog.value.actions.forEach((a) => (v ? s.add(`${m}.${a}`) : s.delete(`${m}.${a}`)))
  checked.value = s
}
const rowAll = (m) => catalog.value.actions.every((a) => has(m, a))

async function save() {
  saving.value = true
  try {
    await http.put(`/roles/${selected.value}/permissions`, { permissions: [...checked.value] })
    ElMessage.success('បានរក្សាទុកសិទ្ធិ')
    await load()
  } finally {
    saving.value = false
  }
}

async function addRole() {
  const { value } = await ElMessageBox.prompt('ឈ្មោះតួនាទីថ្មី', 'បន្ថែមតួនាទី', { inputPattern: /\S+/, inputErrorMessage: 'សូមបញ្ចូលឈ្មោះ' })
  const { data } = await http.post('/roles', { name: value })
  selected.value = data.id
  await load()
}

async function removeRole() {
  await ElMessageBox.confirm(`លុបតួនាទី "${role.value.name}"?`, 'បញ្ជាក់', { type: 'warning' })
  await http.delete(`/roles/${selected.value}`)
  selected.value = null
  await load()
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h2>តួនាទី និងសិទ្ធិ</h2>
      <el-button v-if="auth.can('roles.create')" type="primary" icon="Plus" @click="addRole">បន្ថែមតួនាទី</el-button>
    </div>
    <el-row :gutter="14">
      <el-col :xs="24" :md="6">
        <el-card shadow="never" header="តួនាទី">
          <div v-for="r in roles" :key="r.id" class="role" :class="{ active: r.id === selected }" @click="select(r.id)">
            <div><b>{{ r.name }}</b><div class="muted small">{{ r.description }}</div></div>
            <el-tag v-if="r.is_super" size="small" type="danger">ទាំងអស់</el-tag>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="18">
        <el-card v-if="role" shadow="never">
          <template #header>
            <div class="matrix-head">
              <span>សិទ្ធិរបស់ <b>{{ role.name }}</b></span>
              <span>
                <el-button v-if="!role.is_super && auth.can('roles.delete')" type="danger" plain icon="Delete" @click="removeRole">លុបតួនាទី</el-button>
                <el-button v-if="editable" type="primary" icon="Check" :loading="saving" @click="save">រក្សាទុក</el-button>
              </span>
            </div>
          </template>
          <el-alert v-if="role.is_super" type="info" :closable="false" show-icon title="Super Admin មានសិទ្ធិទាំងអស់ដោយស្វ័យប្រវត្តិ" style="margin-bottom: 10px" />
          <el-table :data="catalog.modules" border size="small" max-height="640">
            <el-table-column label="ម៉ូឌុល" min-width="220" fixed="left">
              <template #default="{ row }">
                <el-checkbox :model-value="rowAll(row.key)" :disabled="!editable" @change="(v) => toggleRow(row.key, v)">{{ row.name }}</el-checkbox>
              </template>
            </el-table-column>
            <el-table-column v-for="a in catalog.actions" :key="a" :label="ACTION_LABEL[a]" width="84" align="center">
              <template #default="{ row }">
                <el-checkbox :model-value="has(row.key, a)" :disabled="!editable" @change="(v) => toggle(row.key, a, v)" />
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.role { display: flex; justify-content: space-between; align-items: center; padding: 10px; border-radius: 6px; cursor: pointer; }
.role:hover { background: #f2f6f4; }
.role.active { background: var(--el-color-primary-light-9); border-left: 3px solid var(--el-color-primary); }
.small { font-size: 12px; }
.matrix-head { display: flex; justify-content: space-between; align-items: center; }
</style>
