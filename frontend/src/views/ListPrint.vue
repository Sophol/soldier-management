<script setup>
/** A4 print of a list exactly as filtered on screen (Export PDF: print, then "Save as PDF"). */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import http from '@/api/http'
import { printedList } from '@/utils/listExport'
import { fmtDateLong, khDigits, todayISO } from '@/utils/format'

const router = useRouter()
const rep = ref(printedList())
const orgName = ref('')
const landscape = ref((rep.value?.columns.length || 0) > 6)
const print = () => window.print()

const pageStyle = document.createElement('style')
document.head.appendChild(pageStyle)
watch(landscape, (v) => { pageStyle.textContent = v ? '@page { size: A4 landscape; }' : '' }, { immediate: true })
onBeforeUnmount(() => pageStyle.remove())

onMounted(async () => {
  orgName.value = (await http.get('/settings', { silent: true }).catch(() => ({ data: {} }))).data.org_name_kh?.value || ''
})
</script>

<template>
  <div class="print-root">
    <div class="toolbar no-print">
      <el-button icon="Back" @click="router.back()">ត្រឡប់ក្រោយ</el-button>
      <el-switch v-model="landscape" active-text="ផ្ដេក (Landscape)" />
      <el-button type="primary" icon="Printer" @click="print">បោះពុម្ព / រក្សាទុកជា PDF</el-button>
    </div>
    <el-empty v-if="!rep" description="គ្មានទិន្នន័យសម្រាប់បោះពុម្ព" />
    <div v-else class="sheet" :class="{ landscape }">
      <div class="kingdom">
        <div class="moul">ព្រះរាជាណាចក្រកម្ពុជា</div>
        <div class="moul">ជាតិ សាសនា ព្រះមហាក្សត្រ</div>
      </div>
      <div class="org moul">{{ orgName }}</div>
      <h1 class="moul">{{ rep.title }}</h1>
      <p v-if="rep.subtitle" class="center">{{ rep.subtitle }}</p>
      <p class="center">ចំនួនសរុប៖ {{ khDigits(rep.rows.length) }}</p>
      <table>
        <thead><tr><th>ល.រ</th><th v-for="c in rep.columns" :key="c">{{ c }}</th></tr></thead>
        <tbody>
          <tr v-for="(r, i) in rep.rows" :key="i">
            <td>{{ khDigits(i + 1) }}</td>
            <td v-for="(v, j) in r" :key="j">{{ v }}</td>
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
.sign { margin-top: 24px; margin-left: auto; width: 80mm; text-align: center; line-height: 2.2; }
@media print {
  .print-root { background: #fff; padding: 0; }
  .sheet, .sheet.landscape { box-shadow: none; margin: 0; padding: 0; width: auto; min-height: auto; }
}
</style>
