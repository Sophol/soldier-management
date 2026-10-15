<script setup>
/** Searchable picker for an incoming (or outgoing) document; v-model is the document id. */
import { ref, watch } from 'vue'
import http from '@/api/http'
import { fmtDate } from '@/utils/format'

const props = defineProps({
  modelValue: { type: [Number, null], default: null },
  direction: { type: String, default: 'incoming' }, // incoming | outgoing
  initialLabel: { type: String, default: '' },
  placeholder: { type: String, default: 'ស្វែងរកតាមលេខ ឬខ្លឹមសារ' },
})
const emit = defineEmits(['update:modelValue'])
const options = ref([])
const loading = ref(false)
const endpoint = () => `/documents/${props.direction}`

function toOption(d) {
  const no = props.direction === 'incoming' ? d.incoming_no : d.outgoing_no
  return { value: d.id, label: `${no} (${fmtDate(d.doc_date)}) ${d.subject}` }
}

async function search(q) {
  loading.value = true
  try {
    const { data } = await http.get(endpoint(), { params: { q, size: 30 } })
    options.value = data.items.map(toOption)
  } finally {
    loading.value = false
  }
}

watch(() => props.modelValue, (id) => {
  if (id && !options.value.some((o) => o.value === id)) {
    options.value = [{ value: id, label: props.initialLabel || `#${id}` }]
  }
}, { immediate: true })
</script>

<template>
  <el-select :model-value="modelValue" filterable remote clearable :remote-method="search" :loading="loading"
             :placeholder="placeholder" style="width: 100%" @change="(v) => emit('update:modelValue', v ?? null)"
             @focus="!options.length && search('')">
    <el-option v-for="o in options" :key="o.value" :value="o.value" :label="o.label" />
  </el-select>
</template>
