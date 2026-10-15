<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '@/api/http'
import { fmtDateLong, khDigits, todayISO } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const rep = ref(null)
const landscape = ref(false)
const print = () => window.print()

// page orientation for the browser print dialog
const pageStyle = document.createElement('style')
document.head.appendChild(pageStyle)
watch(landscape, (v) => { pageStyle.textContent = v ? '@page { size: A4 landscape; }' : '' })
onBeforeUnmount(() => pageStyle.remove())

onMounted(async () => {
  const { key, ...params } = route.query
  rep.value = (await http.get(`/reports/${key}`, { params })).data
  landscape.value = rep.value.columns.length > 7
})

function cell(row, key) {
  const v = row[key]
  if (v == null) return ''
  if (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v)) {
    const [y, m, d] = v.split('-')
    return khDigits(`${d}/${m}/${y}`)
  }
  return typeof v === 'number' ? khDigits(v) : v
}
</script>

<template>
  <div class="print-root">
    <div class="toolbar no-print">
      <el-button icon="Back" @click="router.back()">ត្រឡប់ក្រោយ</el-button>
      <el-switch v-model="landscape" active-text="ផ្ដេក (Landscape)" />
      <el-button type="primary" icon="Printer" @click="print">បោះពុម្ព</el-button>
    </div>
    <div v-if="rep" class="sheet" :class="{ landscape }">
      <div class="kingdom">
        <div class="moul">ព្រះរាជាណាចក្រកម្ពុជា</div>
        <div class="moul">ជាតិ សាសនា ព្រះមហាក្សត្រ</div>
      </div>
      <div class="org moul">{{ rep.org_name }}</div>
      <h1 class="moul">{{ rep.title }}</h1>
      <p class="center">គិតពី{{ fmtDateLong(rep.date_from) }} ដល់{{ fmtDateLong(rep.date_to) }}</p>
      <table>
        <thead><tr><th v-for="c in rep.columns" :key="c.key">{{ c.label }}</th></tr></thead>
        <tbody>
          <tr v-for="(r, i) in rep.rows" :key="i" :class="{ bold: r._level === 1 }">
            <td v-for="c in rep.columns" :key="c.key">{{ cell(r, c.key) }}</td>
          </tr>
          <tr v-if="rep.totals" class="bold">
            <td v-for="c in rep.columns" :key="c.key">{{ cell(rep.totals, c.key) }}</td>
          </tr>
        </tbody>
      </table>
      <div class="sign">
        <div>{{ fmtDateLong(todayISO()) }}</div>
        <div class="moul">អ្នករៀបចំ</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.print-root { background: #e9ecef; min-height: 100vh; padding: 20px 0; }
.toolbar { width: 210mm; margin: 0 auto 12px; display: flex; gap: 12px; align-items: center; }
.sheet { width: 210mm; min-height: 297mm; margin: 0 auto; background: #fff; padding: 12mm; color: #000; font-size: 12px; line-height: 1.7; box-shadow: 0 4px 18px rgba(0, 0, 0, 0.12); }
.sheet.landscape { width: 297mm; min-height: 210mm; }
.kingdom { text-align: center; line-height: 2; font-size: 14px; }
.org { font-size: 13px; }
h1 { text-align: center; font-size: 16px; margin: 10px 0 2px; }
.center { text-align: center; margin: 0 0 8px; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #444; padding: 2px 5px; }
th { background: #eee; }
.bold { font-weight: 700; }
.sign { margin-top: 24px; margin-left: auto; width: 80mm; text-align: center; line-height: 2.2; }
@media print {
  .print-root { background: #fff; padding: 0; }
  .sheet, .sheet.landscape { box-shadow: none; margin: 0; padding: 0; width: auto; min-height: auto; }
}
</style>
