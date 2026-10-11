<script setup>
import { ref, watch } from 'vue'
import http from '@/api/http'

const props = defineProps({
  modelValue: { type: [Number, null], default: null },
  initialLabel: { type: String, default: '' },
  placeholder: { type: String, default: 'ស្វែងរកតាមឈ្មោះ ឬអត្តលេខ' },
})
const emit = defineEmits(['update:modelValue', 'select'])
const options = ref([])
const loading = ref(false)

function toOption(s) {
  return { value: s.id, label: `${s.rank_name || ''} ${s.name_kh} (${s.military_id})`.trim(), soldier: s }
}

async function search(q) {
  loading.value = true
  try {
    const { data } = await http.get('/soldiers', { params: { q, size: 30 } })
    options.value = data.items.map(toOption)
  } finally {
    loading.value = false
  }
}

watch(() => props.modelValue, async (id) => {
  if (id && !options.value.some((o) => o.value === id)) {
    if (props.initialLabel) {
      options.value = [{ value: id, label: props.initialLabel }]
    } else {
      const { data } = await http.get(`/soldiers/${id}`, { silent: true })
      options.value = [toOption(data)]
    }
  }
}, { immediate: true })

function onChange(v) {
  emit('update:modelValue', v ?? null)
  emit('select', options.value.find((o) => o.value === v)?.soldier || null)
}
</script>

<template>
  <el-select :model-value="modelValue" filterable remote clearable :remote-method="search" :loading="loading"
             :placeholder="placeholder" style="width: 100%" @change="onChange" @focus="!options.length && search('')">
    <el-option v-for="o in options" :key="o.value" :value="o.value" :label="o.label" />
  </el-select>
</template>
