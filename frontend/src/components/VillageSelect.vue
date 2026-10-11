<script setup>
/** Province > District > Commune > Village cascading picker; v-model is the village id. */
import { ref, watch } from 'vue'
import http from '@/api/http'

const props = defineProps({ modelValue: { type: [Number, null], default: null } })
const emit = defineEmits(['update:modelValue'])

const sel = ref({ province: null, district: null, commune: null, village: null })
const opts = ref({ provinces: [], districts: [], communes: [], villages: [] })
let syncing = false

async function fetch(path, params) {
  const { data } = await http.get(path, { params: { ...params, size: 1000 } })
  return data.items.map((x) => ({ value: x.id, label: x.type ? `${x.type}${x.name_kh}` : x.name_kh }))
}

async function loadProvinces() {
  if (!opts.value.provinces.length) opts.value.provinces = await fetch('/geo/provinces')
}

async function onProvince(v) {
  sel.value.district = sel.value.commune = sel.value.village = null
  opts.value.districts = v ? await fetch('/geo/districts', { province_id: v }) : []
  opts.value.communes = opts.value.villages = []
  if (!syncing) emit('update:modelValue', null)
}
async function onDistrict(v) {
  sel.value.commune = sel.value.village = null
  opts.value.communes = v ? await fetch('/geo/communes', { district_id: v }) : []
  opts.value.villages = []
  if (!syncing) emit('update:modelValue', null)
}
async function onCommune(v) {
  sel.value.village = null
  opts.value.villages = v ? await fetch('/geo/villages', { commune_id: v }) : []
  if (!syncing) emit('update:modelValue', null)
}
function onVillage(v) {
  emit('update:modelValue', v ?? null)
}

watch(() => props.modelValue, async (id) => {
  await loadProvinces()
  if (!id) {
    if (sel.value.village) sel.value = { province: null, district: null, commune: null, village: null }
    return
  }
  if (id === sel.value.village) return
  syncing = true
  try {
    const { data } = await http.get(`/geo/village-path/${id}`, { silent: true })
    sel.value.province = data.province_id
    await onProvince(data.province_id)
    sel.value.district = data.district_id
    await onDistrict(data.district_id)
    sel.value.commune = data.commune_id
    await onCommune(data.commune_id)
    sel.value.village = data.village_id
  } finally {
    syncing = false
  }
}, { immediate: true })
</script>

<template>
  <div class="geo-grid">
    <el-select v-model="sel.province" filterable clearable placeholder="រាជធានី/ខេត្ត" @change="onProvince">
      <el-option v-for="o in opts.provinces" :key="o.value" v-bind="o" />
    </el-select>
    <el-select v-model="sel.district" filterable clearable placeholder="ស្រុក/ខណ្ឌ" :disabled="!sel.province" @change="onDistrict">
      <el-option v-for="o in opts.districts" :key="o.value" v-bind="o" />
    </el-select>
    <el-select v-model="sel.commune" filterable clearable placeholder="ឃុំ/សង្កាត់" :disabled="!sel.district" @change="onCommune">
      <el-option v-for="o in opts.communes" :key="o.value" v-bind="o" />
    </el-select>
    <el-select v-model="sel.village" filterable clearable placeholder="ភូមិ" :disabled="!sel.commune" @change="onVillage">
      <el-option v-for="o in opts.villages" :key="o.value" v-bind="o" />
    </el-select>
  </div>
</template>

<style scoped>
.geo-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; width: 100%; }
@media (max-width: 900px) { .geo-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
