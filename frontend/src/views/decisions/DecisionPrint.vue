<script setup>
/** Printable decision annex: list of soldiers with old -> new values. */
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '@/api/http'
import { fmtDateLong, khDigits } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const d = ref(null)
const org = ref('')
const print = () => window.print()

onMounted(async () => {
  const [a, b] = await Promise.all([http.get(`/decisions/${route.params.id}`), http.get('/settings')])
  d.value = a.data
  org.value = b.data.org_name_kh?.value || ''
})
</script>

<template>
  <div class="print-root">
    <div class="toolbar no-print">
      <el-button icon="Back" @click="router.back()">ត្រឡប់ក្រោយ</el-button>
      <el-button type="primary" icon="Printer" @click="print">បោះពុម្ព</el-button>
    </div>
    <div v-if="d" class="a4">
      <div class="kingdom">
        <div class="moul">ព្រះរាជាណាចក្រកម្ពុជា</div>
        <div class="moul">ជាតិ សាសនា ព្រះមហាក្សត្រ</div>
        <div class="ornament">❀❀❀</div>
      </div>
      <div class="org moul">{{ org }}</div>
      <div class="no">លេខ៖ {{ khDigits(d.decision_no) }}</div>
      <h1 class="moul">ឧបសម្ព័ន្ធ{{ d.kind_name }}</h1>
      <p class="center">ភ្ជាប់ជាមួយសេចក្ដីសម្រេចលេខ {{ khDigits(d.decision_no) }} {{ fmtDateLong(d.decision_date) }}
        ចូលជាធរមានចាប់ពី{{ fmtDateLong(d.effective_date) }}</p>
      <p v-if="d.status !== 'published'" class="draft">*** {{ d.status_name }} ***</p>
      <table class="grid">
        <thead>
          <tr>
            <th>ល.រ</th><th>អត្តលេខ</th><th>គោត្តនាមនិងនាម</th><th>ភេទ</th>
            <th v-if="d.kind === 'promote'">ឋានន្តរស័ក្តិចាស់</th>
            <th v-if="d.kind === 'promote'">ឋានន្តរស័ក្តិថ្មី</th>
            <th v-if="d.kind !== 'promote'">ឋានន្តរស័ក្តិ</th>
            <th v-if="d.kind !== 'promote'">មុខតំណែង/អង្គភាពចាស់</th>
            <th v-if="d.kind !== 'promote'">មុខតំណែង/អង្គភាពថ្មី</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(i, n) in d.items" :key="i.id">
            <td class="c">{{ khDigits(n + 1) }}</td>
            <td>{{ khDigits(i.military_id) }}</td>
            <td>{{ i.name_kh }}</td>
            <td class="c">{{ i.gender === 'F' ? 'ស្រី' : 'ប្រុស' }}</td>
            <td v-if="d.kind === 'promote'">{{ i.old_rank }}</td>
            <td v-if="d.kind === 'promote'"><b>{{ i.new_rank }}</b></td>
            <td v-if="d.kind !== 'promote'">{{ i.old_rank }}</td>
            <td v-if="d.kind !== 'promote'">{{ [i.old_position, i.old_unit].filter(Boolean).join(' · ') }}</td>
            <td v-if="d.kind !== 'promote'"><b>{{ [i.new_position || i.old_position, i.new_unit || i.old_unit].filter(Boolean).join(' · ') }}</b></td>
          </tr>
        </tbody>
      </table>
      <p>សរុប៖ {{ khDigits(d.items.length) }} នាក់</p>
      <div class="sign">
        <div>{{ fmtDateLong(d.decision_date) }}</div>
        <div class="moul">{{ d.issued_by || 'ប្រធាន' }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.print-root { background: #e9ecef; min-height: 100vh; padding: 20px 0; }
.toolbar { width: 210mm; margin: 0 auto 12px; display: flex; gap: 8px; }
.a4 { width: 210mm; min-height: 297mm; margin: 0 auto; background: #fff; padding: 14mm; font-size: 13px; line-height: 1.8; color: #000; box-shadow: 0 4px 18px rgba(0, 0, 0, 0.12); }
.kingdom { text-align: center; font-size: 14px; line-height: 2; }
.ornament { letter-spacing: 6px; font-size: 11px; }
.org { font-size: 13px; margin-top: 4px; }
.no { margin-top: 4px; }
h1 { text-align: center; font-size: 16px; margin: 12px 0 4px; }
.center { text-align: center; }
.draft { text-align: center; color: #b00; font-weight: 700; }
table { border-collapse: collapse; width: 100%; margin-top: 10px; }
.grid th, .grid td { border: 1px solid #444; padding: 3px 6px; }
.grid th { background: #f0f0f0; }
.c { text-align: center; }
.sign { margin-top: 30px; margin-left: auto; width: 80mm; text-align: center; line-height: 2.2; }
@media print {
  .print-root { background: #fff; padding: 0; }
  .a4 { box-shadow: none; margin: 0; padding: 0; width: auto; min-height: auto; }
}
</style>
