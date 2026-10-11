<script setup>
/** A4 summary profile (ប្រវត្តិរូបសង្ខេប) – printed from the browser. */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '@/api/http'
import AuthImage from '@/components/AuthImage.vue'
import { fmtDateLong, genderText, khDigits } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const s = ref(null)
const org = ref('')
const today = new Date().toISOString().slice(0, 10)
const print = () => window.print()

onMounted(async () => {
  const [p, st] = await Promise.all([http.get(`/soldiers/${route.params.id}/profile`), http.get('/settings')])
  s.value = p.data
  org.value = st.data.org_name_kh?.value || ''
})

const d = (v) => (v ? fmtDateLong(v) : '................')
const k = (v) => (v == null || v === '' ? '................' : khDigits(v))
const history = computed(() => (s.value?.history || []).filter((h) => h.kind !== 'initial').slice(0, 10))
</script>

<template>
  <div class="print-root">
    <div class="toolbar no-print">
      <el-button icon="Back" @click="router.back()">ត្រឡប់ក្រោយ</el-button>
      <el-button type="primary" icon="Printer" @click="print">បោះពុម្ព</el-button>
    </div>

    <div v-if="s" class="a4">
      <div class="kingdom">
        <div class="moul">ព្រះរាជាណាចក្រកម្ពុជា</div>
        <div class="moul">ជាតិ សាសនា ព្រះមហាក្សត្រ</div>
        <div class="ornament">❀❀❀</div>
      </div>
      <div class="org moul">{{ org }}</div>
      <h1 class="moul">ប្រវត្តិរូបសង្ខេប</h1>

      <div class="top">
        <table class="info">
          <tbody>
            <tr><th>អត្តលេខ</th><td>{{ k(s.military_id) }}</td></tr>
            <tr><th>គោត្តនាមនិងនាម</th><td><b>{{ s.name_kh }}</b></td></tr>
            <tr><th>ឈ្មោះជាអក្សរឡាតាំង</th><td>{{ s.name_latin }}</td></tr>
            <tr><th>ភេទ</th><td>{{ genderText(s.gender) }}</td></tr>
            <tr><th>ថ្ងៃខែឆ្នាំកំណើត</th><td>{{ d(s.date_of_birth) }} (អាយុ {{ k(s.age) }} ឆ្នាំ)</td></tr>
            <tr><th>ឋានន្តរស័ក្តិ</th><td>{{ s.rank_name }}</td></tr>
            <tr><th>មុខតំណែង</th><td>{{ s.position_name }}</td></tr>
            <tr><th>អង្គភាព</th><td>{{ s.unit_name }}</td></tr>
          </tbody>
        </table>
        <div class="photo"><AuthImage v-if="s.photo_path" :src="`/soldiers/${s.id}/photo`" /><span v-else>រូបថត ៤x៦</span></div>
      </div>

      <table class="info full">
        <tbody>
          <tr><th>ទីកន្លែងកំណើត</th><td colspan="3">{{ s.birth_village_text || s.birth_place_text }}</td></tr>
          <tr><th>ទីលំនៅបច្ចុប្បន្ន</th><td colspan="3">{{ [s.current_address_text, s.current_village_text].filter(Boolean).join(' ') }}</td></tr>
          <tr><th>លេខអត្តសញ្ញាណប័ណ្ណ</th><td>{{ k(s.national_id) }}</td><th>ទូរសព្ទ</th><td>{{ k(s.phone) }}</td></tr>
          <tr><th>ថ្ងៃចូលបម្រើទ័ព</th><td>{{ d(s.enlistment_date) }}</td><th>រយៈពេលបម្រើការងារ</th><td>{{ k(s.service_length) }}</td></tr>
          <tr><th>ថ្ងៃឡើងស័ក្តិ</th><td>{{ d(s.rank_date) }}</td><th>រយៈពេលឡើងស័ក្តិ</th><td>{{ k(s.time_in_rank) }}</td></tr>
          <tr><th>ថ្ងៃមុខតំណែង</th><td>{{ d(s.position_date) }}</td><th>មកពីស្ថាប័នកងឯកភាព</th><td>{{ s.from_unit_text }}</td></tr>
          <tr><th>កម្រិតវប្បធម៌</th><td>{{ s.education_level_name }}</td><th>ជំនាញឯកទេស</th><td>{{ s.specialty_name }}</td></tr>
          <tr><th>ភាសាបរទេស</th><td>{{ s.languages.map((l) => l.language_name).join(', ') }}</td><th>ប្រភេទឈាម</th><td>{{ s.blood_type_name }}</td></tr>
          <tr><th>ឆ្លងប្រយុទ្ធ</th><td>{{ s.combat_veteran ? 'បាទ/ចាស' : 'ទេ' }}</td><th>ស្ថានភាព</th><td>{{ s.status_name }}</td></tr>
          <tr><th>ស្ថានភាពគ្រួសារ</th><td>{{ s.marital_status_name }}</td><th>ចំនួនកូន</th><td>{{ k(s.children_count) }} នាក់</td></tr>
          <tr><th>ឈ្មោះប្ដី/ប្រពន្ធ</th><td>{{ s.spouse_name }}</td><th>មុខរបរ</th><td>{{ s.spouse_job_name }}</td></tr>
          <tr><th>ឈ្មោះឪពុក</th><td>{{ s.father_name }}</td><th>ឈ្មោះម្ដាយ</th><td>{{ s.mother_name }}</td></tr>
        </tbody>
      </table>

      <template v-if="history.length">
        <h3>ប្រវត្តិការងារ</h3>
        <table class="grid">
          <thead><tr><th>កាលបរិច្ឆេទ</th><th>ឋានន្តរស័ក្តិ</th><th>មុខតំណែង</th><th>អង្គភាព</th></tr></thead>
          <tbody>
            <tr v-for="h in history" :key="h.id">
              <td>{{ d(h.effective_date) }}</td><td>{{ h.new_rank }}</td><td>{{ h.new_position }}</td><td>{{ h.new_unit }}</td>
            </tr>
          </tbody>
        </table>
      </template>

      <template v-if="s.educations.length || s.trainings.length">
        <h3>ការសិក្សា និងបណ្ដុះបណ្ដាល</h3>
        <table class="grid">
          <thead><tr><th>កម្រិត/វគ្គ</th><th>ជំនាញ</th><th>គ្រឹះស្ថាន</th><th>រយៈពេល</th></tr></thead>
          <tbody>
            <tr v-for="e in s.educations" :key="`e${e.id}`">
              <td>{{ e.education_level_name }}</td><td>{{ e.specialty_text }}</td><td>{{ e.institution }}</td>
              <td>{{ k(e.start_date?.slice(0, 4)) }} - {{ k(e.end_date?.slice(0, 4)) }}</td>
            </tr>
            <tr v-for="t in s.trainings" :key="`t${t.id}`">
              <td>{{ t.name }}</td><td>{{ t.course_type === 'long' ? 'រយៈពេលវែង' : 'រយៈពេលខ្លី' }}</td><td>{{ t.institution }}</td>
              <td>{{ k(t.start_date) }} - {{ k(t.end_date) }}</td>
            </tr>
          </tbody>
        </table>
      </template>

      <template v-if="s.awards.length">
        <h3>ការសរសើរ និងគ្រឿងឥស្សរិយយស</h3>
        <table class="grid">
          <thead><tr><th>ប្រភេទ</th><th>លេខលិខិត</th><th>កាលបរិច្ឆេទ</th></tr></thead>
          <tbody><tr v-for="a in s.awards" :key="a.id"><td>{{ a.award_type_name }}</td><td>{{ k(a.decision_no) }}</td><td>{{ d(a.decision_date) }}</td></tr></tbody>
        </table>
      </template>

      <div class="sign">
        <div>{{ fmtDateLong(today) }}</div>
        <div class="moul">ហត្ថលេខាសាមីខ្លួន</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.print-root { background: #e9ecef; min-height: 100vh; padding: 20px 0; }
.toolbar { width: 210mm; margin: 0 auto 12px; display: flex; gap: 8px; }
.a4 { width: 210mm; min-height: 297mm; margin: 0 auto; background: #fff; padding: 14mm 14mm; font-size: 13px; line-height: 1.75;
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.12); color: #000; }
.kingdom { text-align: center; font-size: 14px; line-height: 2; }
.ornament { letter-spacing: 6px; font-size: 11px; }
.org { font-size: 13px; margin-top: 4px; }
h1 { text-align: center; font-size: 18px; margin: 8px 0 14px; text-decoration: underline; text-underline-offset: 8px; }
h3 { font-size: 14px; margin: 14px 0 6px; }
.top { display: flex; gap: 14px; align-items: flex-start; }
.photo { width: 32mm; height: 42mm; border: 1px solid #333; display: flex; align-items: center; justify-content: center; flex-shrink: 0; overflow: hidden; color: #888; }
.photo :deep(img) { width: 100%; height: 100%; object-fit: cover; }
table { border-collapse: collapse; width: 100%; }
.info th { text-align: left; font-weight: 600; width: 42mm; padding: 2px 6px; vertical-align: top; }
.info td { padding: 2px 6px; border-bottom: 1px dotted #999; }
.info.full { margin-top: 8px; }
.info.full th { width: 38mm; }
.grid th, .grid td { border: 1px solid #555; padding: 3px 6px; }
.grid th { background: #f0f0f0; }
.sign { margin-top: 26px; margin-left: auto; width: 70mm; text-align: center; line-height: 2.2; }
@media print {
  .print-root { background: #fff; padding: 0; }
  .a4 { box-shadow: none; margin: 0; padding: 0; width: auto; min-height: auto; }
}
</style>
