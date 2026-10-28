<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import CrudPage from '@/components/CrudPage.vue'
import SoldierSelect from '@/components/SoldierSelect.vue'
import { useLookups } from '@/stores/lookups'
import { fmtDate } from '@/utils/format'

const route = useRoute()
const type = computed(() => route.params.type)
const viewing = ref(null)
const lookups = useLookups()
const LEVEL = { basic: 'វគ្គបណ្ដុះបណ្ដាល', refresher: 'វគ្គបំប៉ន' }
const levelOptions = Object.entries(LEVEL).map(([value, label]) => ({ value, label }))
const SECTOR = { military: 'យោធា', civil: 'ស៊ីវិល' }
const sectorOptions = Object.entries(SECTOR).map(([value, label]) => ({ value, label }))
const cambodiaId = () => lookups.list('countries').find((c) => c.name_en === 'Cambodia')?.id
const abroad = (r) => !!r.country_id && r.country_id !== cambodiaId()
const COURSE_STATUS = [{ value: 'upcoming', label: 'មិនទាន់ចាប់ផ្ដើម' }, { value: 'ongoing', label: 'កំពុងរៀន' }, { value: 'finished', label: 'បានបញ្ចប់' }]
const PARTICIPANT_STATUS = { studying: 'កំពុងរៀន', completed: 'បញ្ចប់', dropped: 'ឈប់' }
const participantOptions = Object.entries(PARTICIPANT_STATUS).map(([value, label]) => ({ value, label }))
const STATUS_TAG = { upcoming: 'info', ongoing: 'warning', finished: 'success', studying: 'warning', completed: 'success', dropped: 'danger' }

const config = computed(() => ({
  title: type.value === 'long' ? 'វគ្គបណ្ដុះបណ្ដាលរយៈពេលវែង' : 'វគ្គបណ្ដុះបណ្ដាលរយៈពេលខ្លី',
  endpoint: '/training/courses', auditFilters: true, module: 'training', attachments: 'training', formWidth: '980px',
  fixedParams: { course_type: type.value },
  columns: [
    { key: 'name', label: 'ឈ្មោះវគ្គ', minWidth: 220 },
    { key: 'institution', label: 'គ្រឹះស្ថាន', minWidth: 160 },
    { key: 'level', label: 'ប្រភេទវគ្គ', width: 120, value: (r) => LEVEL[r.level] },
    { key: 'sector', label: 'ផ្នែក', width: 100, value: (r) => SECTOR[r.sector] },
    { key: 'country', label: 'ប្រទេស', width: 120, value: (r, lk) => lk.list('countries').find((c) => c.id === r.country_id)?.name_kh },
    { key: 'where', label: 'ក្នុង/ក្រៅប្រទេស', width: 130, value: (r, lk) => (abroad(r, lk) ? 'ក្រៅប្រទេស' : 'ក្នុងប្រទេស'), tag: (r) => (abroad(r, lookups) ? 'warning' : 'info') },
    { key: 'start_date', label: 'ចាប់ពី', type: 'date', width: 110 },
    { key: 'end_date', label: 'ដល់', type: 'date', width: 110 },
    { key: 'participant_count', label: 'ចំនួនសិក្ខាកាម', width: 120 },
    { key: 'status_name', label: 'ស្ថានភាព', width: 130, tag: (r) => STATUS_TAG[r.status] || 'info' },
  ],
  filters: [{ key: 'level', label: 'ប្រភេទវគ្គ', type: 'select', width: '150px', options: levelOptions },
    { key: 'sector', label: 'ផ្នែក', type: 'select', width: '130px', options: sectorOptions },
    { key: 'specialty_id', label: 'ជំនាញ', type: 'select', options: 'specialties' },
    { key: 'abroad', label: 'ក្នុង/ក្រៅប្រទេស', type: 'select', width: '140px', options: [{ value: 'no', label: 'ក្នុងប្រទេស' }, { value: 'yes', label: 'ក្រៅប្រទេស' }] },
    { key: 'country_id', label: 'ប្រទេស', type: 'select', width: '160px', options: 'countries' },
    { key: 'institution', label: 'ស្ថាប័នបណ្ដុះបណ្ដាល', width: '170px' },
    { key: 'status', label: 'ស្ថានភាពវគ្គ', type: 'select', width: '150px', options: COURSE_STATUS },
    { key: 'participant_status', label: 'សិក្ខាកាម', type: 'select', width: '130px', options: participantOptions },
    { key: 'date_from', label: 'ចាប់ផ្ដើមពី', type: 'date', width: '150px' }, { key: 'date_to', label: 'ដល់', type: 'date', width: '150px' },
    { key: 'end_from', label: 'បញ្ចប់ពី', type: 'date', width: '150px' }, { key: 'end_to', label: 'ដល់', type: 'date', width: '150px' }],
  fields: [
    { key: 'name', label: 'ឈ្មោះវគ្គ', required: true, span: 16 },
    { key: 'level', label: 'ប្រភេទវគ្គ', type: 'select', required: true, default: 'basic', options: levelOptions, span: 4 },
    { key: 'sector', label: 'ផ្នែក', type: 'select', required: true, default: 'military', options: sectorOptions, span: 4 },
    { key: 'specialty_id', label: 'ជំនាញឯកទេស', type: 'select', options: 'specialties', span: 8 },
    { key: 'institution', label: 'គ្រឹះស្ថានបណ្ដុះបណ្ដាល', span: 8 },
    { key: 'country_id', label: 'ប្រទេស', type: 'select', options: 'countries', span: 8 },
    { key: 'start_date', label: 'ថ្ងៃចាប់ផ្ដើម', type: 'date', span: 8 },
    { key: 'end_date', label: 'ថ្ងៃបញ្ចប់', type: 'date', span: 8 },
    { key: 'notes', label: 'កំណត់សម្គាល់', type: 'textarea', rows: 2 },
    { key: 'participants', label: '', type: 'hidden', default: [], showIf: () => false },
  ],
  beforeSave: (p) => {
    p.participants = (p.participants || []).filter((x) => x.soldier_id)
      .map(({ soldier_id, status, result, certificate_no }) => ({ soldier_id, status: status || 'studying', result, certificate_no }))
  },
}))

function label(p) {
  return p.soldier_name ? `${p.rank_name || ''} ${p.soldier_name} (${p.military_id})` : ''
}
</script>

<template>
  <CrudPage :key="type" :config="config">
    <template #row-actions="{ row }">
      <el-tooltip content="បញ្ជីសិក្ខាកាម"><el-button link type="primary" icon="User" @click="viewing = row" /></el-tooltip>
    </template>
    <template #form-extra="{ form }">
      <div class="section-title">សិក្ខាកាម</div>
      <el-table :data="form.participants" border size="small" empty-text="មិនទាន់មានសិក្ខាកាម">
        <el-table-column label="យោធិន" min-width="280">
          <template #default="{ row }"><SoldierSelect v-model="row.soldier_id" :initial-label="label(row)" /></template>
        </el-table-column>
        <el-table-column label="ស្ថានភាព" width="130">
          <template #default="{ row }">
            <el-select v-model="row.status"><el-option v-for="o in participantOptions" :key="o.value" :value="o.value" :label="o.label" /></el-select>
          </template>
        </el-table-column>
        <el-table-column label="លទ្ធផល/ថ្នាក់" width="160"><template #default="{ row }"><el-input v-model="row.result" /></template></el-table-column>
        <el-table-column label="លេខសញ្ញាបត្រ" width="160"><template #default="{ row }"><el-input v-model="row.certificate_no" /></template></el-table-column>
        <el-table-column width="50"><template #default="{ $index }"><el-button link type="danger" icon="Delete" @click="form.participants.splice($index, 1)" /></template></el-table-column>
      </el-table>
      <el-button icon="Plus" size="small" style="margin-top: 8px"
                 @click="form.participants.push({ soldier_id: null, status: 'studying', result: '', certificate_no: '' })">បន្ថែមសិក្ខាកាម</el-button>
    </template>
  </CrudPage>

  <el-dialog :model-value="!!viewing" :title="viewing?.name" width="800px" @close="viewing = null">
    <p v-if="viewing" class="muted">{{ viewing.institution }} · {{ fmtDate(viewing.start_date) }} - {{ fmtDate(viewing.end_date) }}</p>
    <el-table v-if="viewing" :data="viewing.participants" border size="small" empty-text="គ្មាន">
      <el-table-column type="index" label="ល.រ" width="55" />
      <el-table-column prop="military_id" label="អត្តលេខ" width="110" />
      <el-table-column prop="rank_name" label="ឋានន្តរស័ក្តិ" width="130" />
      <el-table-column prop="soldier_name" label="គោត្តនាមនិងនាម" />
      <el-table-column prop="unit_name" label="អង្គភាព" />
      <el-table-column label="ស្ថានភាព" width="100">
        <template #default="{ row }"><el-tag size="small" :type="STATUS_TAG[row.status]">{{ PARTICIPANT_STATUS[row.status] }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="result" label="លទ្ធផល/ថ្នាក់" width="120" />
    </el-table>
  </el-dialog>
</template>
