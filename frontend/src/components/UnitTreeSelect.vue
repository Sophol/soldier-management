<script setup>
import { computed } from 'vue'
import { useLookups } from '@/stores/lookups'

const props = defineProps({
  modelValue: { type: [Number, null], default: null },
  placeholder: { type: String, default: 'ជ្រើសរើសអង្គភាព' },
  maxLevel: { type: Number, default: 4 },
  excludeId: { type: Number, default: null },
})
const emit = defineEmits(['update:modelValue', 'change'])
const lookups = useLookups()

const data = computed(() => {
  const map = (nodes) => nodes
    .filter((n) => n.id !== props.excludeId && n.level <= props.maxLevel)
    .map((n) => ({ value: n.id, label: n.name_kh, disabled: !n.active, children: map(n.children || []) }))
  return map(lookups.unitTree)
})

const value = computed({
  get: () => props.modelValue,
  set: (v) => { emit('update:modelValue', v ?? null); emit('change', v ?? null) },
})
</script>

<template>
  <el-tree-select v-model="value" :data="data" check-strictly filterable clearable default-expand-all
                  :placeholder="placeholder" :render-after-expand="false" style="width: 100%" />
</template>
