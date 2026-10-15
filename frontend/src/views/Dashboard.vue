<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import http from '@/api/http'
import { num } from '@/utils/format'

use([CanvasRenderer, BarChart, LineChart, PieChart, GridComponent, LegendComponent, TooltipComponent])

const router = useRouter()
const data = ref(null)
const loading = ref(true)
const PALETTE = ['#24614b', '#c9a227', '#4f7cac', '#b5543c', '#7a6aa8', '#5c9e8f', '#9a8f6b']

onMounted(async () => {
  try {
    data.value = (await http.get('/dashboard/summary')).data
  } finally {
    loading.value = false
  }
})

const pie = (obj) => ({
  color: PALETTE,
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: { bottom: 0, type: 'scroll' },
  series: [{ type: 'pie', radius: ['45%', '70%'], center: ['50%', '45%'], itemStyle: { borderColor: '#fff', borderWidth: 2 },
    label: { formatter: '{c}' }, data: Object.entries(obj || {}).map(([name, value]) => ({ name, value })) }],
})

const bar = (obj) => ({
  color: PALETTE,
  tooltip: { trigger: 'axis' },
  grid: { left: 10, right: 20, top: 10, bottom: 10, containLabel: true },
  xAxis: { type: 'value', minInterval: 1 },
  yAxis: { type: 'category', data: Object.keys(obj || {}), axisLabel: { width: 160, overflow: 'truncate' } },
  series: [{ type: 'bar', data: Object.values(obj || {}), barMaxWidth: 22, label: { show: true, position: 'right' } }],
})

const movement = computed(() => {
  const m = data.value?.movements
  if (!m) return {}
  return {
    color: ['#24614b', '#b5543c'],
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    grid: { left: 10, right: 20, top: 36, bottom: 10, containLabel: true },
    xAxis: { type: 'category', data: m.months },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{ name: 'កើន', type: 'bar', data: m.in, barMaxWidth: 18 }, { name: 'ថយ', type: 'bar', data: m.out, barMaxWidth: 18 }],
  }
})

const cards = computed(() => {
  const d = data.value
  if (!d) return []
  return [
    { label: 'យោធិនកំពុងបម្រើការ', value: d.total_active, icon: 'User', color: '#24614b', to: '/soldiers' },
    { label: 'យោធិនសរុប (គ្រប់ស្ថានភាព)', value: d.total_all, icon: 'UserFilled', color: '#4f7cac', to: '/soldiers' },
    { label: 'ឯកសារចូល (ខែនេះ)', value: d.documents.incoming_month, icon: 'Download', color: '#7a6aa8', to: '/documents/incoming' },
    { label: 'ឯកសារចេញ (ខែនេះ)', value: d.documents.outgoing_month, icon: 'Upload', color: '#c9a227', to: '/documents/outgoing' },
  ]
})

const alerts = computed(() => {
  const a = data.value?.alerts
  if (!a) return []
  return [
    { label: 'គ្រប់លក្ខខណ្ឌដំឡើងឋានន្តរស័ក្តិ', value: a.promotion_due, type: 'success', to: '/reports?key=promotion_due' },
    { label: 'ជិតដល់អាយុចូលនិវត្តន៍', value: a.retirement_due, type: 'warning', to: '/reports?key=retirement_due' },
    { label: 'ទណ្ឌកម្មផុតកំណត់ក្នុង ៣០ ថ្ងៃ', value: a.discipline_ending, type: 'info', to: '/discipline' },
    { label: 'ខ្វះរូបថត', value: a.missing_photo, type: 'danger', to: '/soldiers' },
    { label: 'ខ្វះលេខអត្តសញ្ញាណប័ណ្ណ', value: a.missing_national_id, type: 'danger', to: '/soldiers' },
    { label: 'មិនទាន់មានអង្គភាព', value: a.missing_unit, type: 'danger', to: '/soldiers' },
  ]
})

const pending = computed(() => {
  const p = data.value?.pending_decisions || {}
  return [
    { label: 'តែងតាំងមុខតំណែង', value: p.appoint, to: '/decisions/appoint' },
    { label: 'ផ្លាស់ប្ដូរ', value: p.transfer, to: '/decisions/transfer' },
    { label: 'ដំឡើងឋានន្តរស័ក្តិ', value: p.promote, to: '/decisions/promote' },
  ]
})
</script>

<template>
  <div v-loading="loading" class="page">
    <div class="page-head"><h2>ផ្ទាំងគ្រប់គ្រង</h2></div>
    <template v-if="data">
      <el-row :gutter="14">
        <el-col v-for="c in cards" :key="c.label" :xs="24" :sm="12" :lg="6">
          <el-card shadow="hover" class="stat" @click="router.push(c.to)">
            <div class="stat-icon" :style="{ background: c.color }"><el-icon :size="24"><component :is="c.icon" /></el-icon></div>
            <div>
              <div class="stat-value">{{ num(c.value) }}</div>
              <div class="muted">{{ c.label }}</div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="14">
        <el-col :xs="24" :lg="16">
          <el-card shadow="never" header="ការជូនដំណឹង">
            <div class="alerts">
              <div v-for="a in alerts" :key="a.label" class="alert-item" @click="router.push(a.to)">
                <el-tag :type="a.type" effect="dark" round>{{ num(a.value) }}</el-tag>
                <span>{{ a.label }}</span>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :xs="24" :lg="8">
          <el-card shadow="never" header="សេចក្ដីសម្រេចកំពុងរង់ចាំអនុម័ត">
            <div v-for="p in pending" :key="p.label" class="alert-item" @click="router.push(p.to)">
              <el-tag type="warning" round>{{ num(p.value) }}</el-tag><span>{{ p.label }}</span>
            </div>
            <div v-if="data.workflow" class="alert-item">
              <el-tag type="primary" effect="dark" round>{{ num(data.workflow.waiting_for_me) }}</el-tag><span>រង់ចាំខ្ញុំអនុម័ត</span>
            </div>
            <div v-if="data.workflow?.overdue" class="alert-item">
              <el-tag type="danger" effect="dark" round>{{ num(data.workflow.overdue) }}</el-tag><span>នៅជាប់ដំណាក់កាលយូរលើសកំណត់</span>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="14">
        <el-col :xs="24" :md="8">
          <el-card shadow="never" header="តាមថ្នាក់ឋានន្តរស័ក្តិ"><v-chart class="chart" :option="pie(data.by_rank_class)" autoresize /></el-card>
        </el-col>
        <el-col :xs="24" :md="8">
          <el-card shadow="never" header="តាមភេទ"><v-chart class="chart" :option="pie(data.by_gender)" autoresize /></el-card>
        </el-col>
        <el-col :xs="24" :md="8">
          <el-card shadow="never" header="តាមស្ថានភាព"><v-chart class="chart" :option="pie(data.by_status)" autoresize /></el-card>
        </el-col>
      </el-row>

      <el-row :gutter="14">
        <el-col :xs="24" :lg="12">
          <el-card shadow="never" header="តាមស្ថាប័នកងឯកភាព"><v-chart class="chart" :option="bar(data.by_institution)" autoresize /></el-card>
        </el-col>
        <el-col :xs="24" :lg="12">
          <el-card shadow="never" header="កើនថយ ១២ ខែចុងក្រោយ"><v-chart class="chart" :option="movement" autoresize /></el-card>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<style scoped>
.el-row { row-gap: 14px; }
.stat { cursor: pointer; }
.stat :deep(.el-card__body) { display: flex; gap: 14px; align-items: center; }
.stat-icon { width: 50px; height: 50px; border-radius: 10px; color: #fff; display: flex; align-items: center; justify-content: center; }
.stat-value { font-size: 26px; font-weight: 600; }
.alerts { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 10px; }
.alert-item { display: flex; gap: 10px; align-items: center; padding: 8px 10px; border-radius: 8px; cursor: pointer; }
.alert-item:hover { background: #f2f6f4; }
.chart { height: 280px; }
</style>
