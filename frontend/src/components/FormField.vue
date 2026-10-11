<script setup>
/** Renders one input from a field definition used by CrudPage / filters. */
import { computed } from 'vue'
import { useLookups } from '@/stores/lookups'
import UnitTreeSelect from './UnitTreeSelect.vue'
import SoldierSelect from './SoldierSelect.vue'
import VillageSelect from './VillageSelect.vue'

const props = defineProps({
  field: { type: Object, required: true },
  modelValue: { default: null },
  row: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['update:modelValue'])
const lookups = useLookups()

const disabled = computed(() => (typeof props.field.disabled === 'function' ? props.field.disabled(props.row) : !!props.field.disabled))
const value = computed({ get: () => props.modelValue, set: (v) => emit('update:modelValue', v) })

/** options: [{value,label}] | 'lookup:<category>' | '<store key>' | (row) => [...] */
const options = computed(() => {
  const o = props.field.options
  if (!o) return []
  if (typeof o === 'function') return o(props.row, lookups)
  if (Array.isArray(o)) return o
  const key = o.startsWith('lookup:') ? o.slice(7) : o
  return lookups.list(key).map((x) => ({ value: x.id, label: x.name_kh }))
})
</script>

<template>
  <el-input v-if="!field.type || field.type === 'text'" :disabled="disabled" v-model="value" :placeholder="field.placeholder" clearable />
  <el-input v-else-if="field.type === 'textarea'" :disabled="disabled" v-model="value" type="textarea" :rows="field.rows || 3" />
  <el-input-number :disabled="disabled" v-else-if="field.type === 'number'" v-model="value" :min="field.min ?? 0" :max="field.max"
                   controls-position="right" style="width: 100%" />
  <el-date-picker v-else-if="field.type === 'date'" :disabled="disabled" v-model="value" type="date" value-format="YYYY-MM-DD"
                  format="DD/MM/YYYY" style="width: 100%" placeholder="ថ្ងៃ/ខែ/ឆ្នាំ" />
  <el-date-picker v-else-if="field.type === 'year'" v-model="value" type="year" value-format="YYYY" style="width: 100%" />
  <el-switch v-else-if="field.type === 'switch'" v-model="value" />
  <el-select v-else-if="field.type === 'select'" :disabled="disabled" v-model="value" filterable clearable :multiple="field.multiple"
             :placeholder="field.placeholder || 'ជ្រើសរើស'" style="width: 100%">
    <el-option v-for="o in options" :key="o.value" :value="o.value" :label="o.label" />
  </el-select>
  <UnitTreeSelect v-else-if="field.type === 'unit'" v-model="value" />
  <SoldierSelect v-else-if="field.type === 'soldier'" v-model="value"
                 :initial-label="row.soldier_name ? `${row.rank_name || ''} ${row.soldier_name} (${row.military_id})` : ''" />
  <VillageSelect v-else-if="field.type === 'village'" v-model="value" />
  <el-input v-else v-model="value" />
</template>
