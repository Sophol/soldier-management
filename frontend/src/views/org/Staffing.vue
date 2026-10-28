<script setup>
/** Staffing table (ក្របខណ្ឌ): authorised positions per unit with quota, rank range, salary, filled and vacant. */
import { computed, ref } from 'vue'
import CrudPage from '@/components/CrudPage.vue'
import UnitTreeSelect from '@/components/UnitTreeSelect.vue'
import { useLookups } from '@/stores/lookups'
import { num } from '@/utils/format'

const lookups = useLookups()
const unitId = ref(null)
const rankOptions = () => lookups.list('ranks').map((r) => ({ value: r.id, label: `${r.name_kh} (${r.rank_class_name})` }))
const positionOptions = () => lookups.list('positions').map((p) => ({ value: p.id, label: p.name_kh }))
const money = (v) => (v == null ? '' : num(Number(v).toLocaleString('en-US')))

const config = computed(() => ({
  title: 'ក្របខណ្ឌមុខតំណែងតាមអង្គភាព', endpoint: '/unit-positions', module: 'positions', formWidth: '720px',
  fixedParams: { unit_id: unitId.value },
  columns: [
    ...(unitId.value ? [] : [{ key: 'unit_name', label: 'អង្គភាព', minWidth: 180 }]),
    { key: 'position_name', label: 'មុខតំណែង', minWidth: 180 },
    { key: 'quota', label: 'ចំនួនក្របខណ្ឌ', width: 120 },
    { key: 'filled', label: 'កំពុងមាន', width: 100 },
    { key: 'vacant', label: 'ទំនេរ', width: 90 },
    { key: 'ranks', label: 'បណ្ដាស័ក្តិ', minWidth: 200, value: (r) => (r.min_rank_name || r.max_rank_name ? `${r.min_rank_name || '...'} – ${r.max_rank_name || '...'}` : '') },
    { key: 'salary_effective', label: 'ប្រាក់បៀវត្សមុខតំណែង', width: 170, value: (r) => money(r.salary_effective) },
  ],
  // ក្របខណ្ឌទំនេរ / ខ្វះ / លើស
  filters: [{ key: 'position_id', label: 'មុខតំណែង', type: 'select', options: positionOptions, width: '200px' },
    { key: 'fill', label: 'ក្របខណ្ឌ', type: 'select', width: '170px', options: [
      { value: 'vacant', label: 'នៅទំនេរ (ខ្វះ)' }, { value: 'full', label: 'គ្រប់ចំនួន' }, { value: 'over', label: 'លើសក្របខណ្ឌ' }] }],
  fields: [
    { key: 'unit_id', label: 'អង្គភាព', type: 'unit', required: true },
    { key: 'position_id', label: 'មុខតំណែង', type: 'select', required: true, options: positionOptions, span: 12 },
    { key: 'quota', label: 'ចំនួនក្របខណ្ឌ', type: 'number', default: 1, required: true, span: 12 },
    { key: 'min_rank_id', label: 'ឋានន្តរស័ក្តិទាបបំផុត', type: 'select', options: rankOptions, span: 12 },
    { key: 'max_rank_id', label: 'ឋានន្តរស័ក្តិខ្ពស់បំផុត', type: 'select', options: rankOptions, span: 12 },
    { key: 'salary', label: 'ប្រាក់បៀវត្សមុខតំណែង (រៀល) — ទុកទំនេរ = តាមមុខតំណែង', type: 'number', span: 12 },
    { key: 'notes', label: 'កំណត់សម្គាល់', type: 'textarea', rows: 2 },
  ],
}))
</script>

<template>
  <div>
    <el-card shadow="never" class="unit-pick">
      <span class="label">អង្គភាព</span>
      <div class="picker"><UnitTreeSelect v-model="unitId" placeholder="គ្រប់អង្គភាព" /></div>
      <span class="muted">ពេលអនុម័តការតែងតាំង/ផ្លាស់ប្ដូរ ប្រព័ន្ធនឹងព្រមាន បើលើសចំនួនក្របខណ្ឌ ឬឋានន្តរស័ក្តិមិនស្រប។</span>
    </el-card>
    <CrudPage :config="config">
      <template #cell-vacant="{ row }">
        <el-tag :type="row.vacant < 0 ? 'danger' : row.vacant > 0 ? 'warning' : 'success'" size="small">{{ num(row.vacant) }}</el-tag>
      </template>
    </CrudPage>
  </div>
</template>

<style scoped>
.unit-pick { margin: 20px 20px 0; }
.unit-pick :deep(.el-card__body) { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.label { font-weight: 700; }
.picker { width: 360px; max-width: 100%; }
</style>
