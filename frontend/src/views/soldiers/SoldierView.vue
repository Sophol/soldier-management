<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '@/api/http'
import { useAuth } from '@/stores/auth'
import AuthImage from '@/components/AuthImage.vue'
import FileAttachments from '@/components/FileAttachments.vue'
import { fmtDate, genderText, num } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const auth = useAuth()
const s = ref(null)
const tab = ref('info')
const KIND = { initial: 'ទិន្នន័យដំបូង', appoint: 'តែងតាំង', transfer: 'ផ្លាស់ប្ដូរ', promote: 'ដំឡើងស័ក្តិ', correction: 'កែតម្រូវ' }
const KIND_TYPE = { initial: 'info', appoint: 'primary', transfer: 'warning', promote: 'success', correction: 'danger' }
const EDU_KIND = { general: 'វប្បធម៌ទូទៅ', specialty: 'ជំនាញឯកទេស', other: 'ក្រៅពីជំនាញ' }

onMounted(async () => {
  s.value = (await http.get(`/soldiers/${route.params.id}/profile`)).data
})

const change = (a, b) => (b ? `${a || '-'} → ${b}` : '')
const money = (v) => (v == null ? '' : `${num(Number(v).toLocaleString('en-US'))} រៀល`)
</script>

<template>
  <div v-if="s" class="page">
    <div class="page-head">
      <h2>ប្រវត្តិរូបយោធិន</h2>
      <div class="head-actions">
        <el-button icon="Back" @click="router.push('/soldiers')">បញ្ជីយោធិន</el-button>
        <el-button v-if="auth.can('soldiers.print')" icon="Printer" @click="router.push(`/soldiers/${s.id}/print`)">បោះពុម្ព A4</el-button>
        <el-button v-if="auth.can('soldiers.update')" type="primary" icon="Edit" @click="router.push(`/soldiers/${s.id}/edit`)">កែប្រែ</el-button>
      </div>
    </div>

    <el-card shadow="never">
      <div class="header">
        <div class="photo"><AuthImage v-if="s.photo_path" :src="`/soldiers/${s.id}/photo`" /><AuthImage v-else /></div>
        <div class="head-info">
          <div class="name">{{ s.rank_name }} <b>{{ s.name_kh }}</b> <span class="muted">{{ s.name_latin }}</span></div>
          <div class="chips">
            <el-tag>អត្តលេខ {{ s.military_id }}</el-tag>
            <el-tag v-if="s.status_name" :type="['retired','category2','separated'].includes(s.status_code) ? 'info' : 'success'">{{ s.status_name }}</el-tag>
            <el-tag type="warning">{{ s.position_name || 'គ្មានមុខតំណែង' }}</el-tag>
            <el-tag type="info">{{ s.unit_name || 'មិនទាន់មានអង្គភាព' }}</el-tag>
          </div>
          <el-descriptions :column="4" size="small" class="quick">
            <el-descriptions-item label="ភេទ">{{ genderText(s.gender) }}</el-descriptions-item>
            <el-descriptions-item label="អាយុ">{{ num(s.age) }} ឆ្នាំ</el-descriptions-item>
            <el-descriptions-item label="រយៈពេលបម្រើការងារ">{{ num(s.service_length) }}</el-descriptions-item>
            <el-descriptions-item label="រយៈពេលឡើងស័ក្តិ">{{ num(s.time_in_rank) }}</el-descriptions-item>
            <el-descriptions-item label="រយៈពេលមុខតំណែង">{{ num(s.time_in_position) }}</el-descriptions-item>
            <el-descriptions-item label="ចំណុះស្ថាប័នកងឯកភាព">{{ s.institution_name }}</el-descriptions-item>
            <el-descriptions-item label="ស្ថាប័នកងឯកភាព-អង្គភាព" :span="2">{{ s.unit_path }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-tabs v-model="tab">
        <el-tab-pane label="ព័ត៌មានលម្អិត" name="info">
          <el-descriptions :column="3" border>
            <el-descriptions-item label="ថ្ងៃខែឆ្នាំកំណើត">{{ fmtDate(s.date_of_birth) }}</el-descriptions-item>
            <el-descriptions-item label="អត្តសញ្ញាណប័ណ្ណ">{{ s.national_id }}</el-descriptions-item>
            <el-descriptions-item label="ទូរសព្ទ">{{ s.phone }}</el-descriptions-item>
            <el-descriptions-item label="ផុតកំណត់អត្តសញ្ញាណប័ណ្ណ">{{ fmtDate(s.national_id_expiry) }}</el-descriptions-item>
            <el-descriptions-item label="សញ្ជាតិ">{{ s.nationality }}</el-descriptions-item>
            <el-descriptions-item label="ជនជាតិ">{{ s.ethnicity }}</el-descriptions-item>
            <el-descriptions-item label="ទីកន្លែងកំណើត" :span="3">{{ s.birth_village_text || s.birth_place_text }}</el-descriptions-item>
            <el-descriptions-item label="ទីលំនៅបច្ចុប្បន្ន" :span="3">{{ [s.current_address_text, s.current_village_text].filter(Boolean).join(' ') }}</el-descriptions-item>
            <el-descriptions-item label="ថ្ងៃចូលបម្រើទ័ព">{{ fmtDate(s.enlistment_date) }}</el-descriptions-item>
            <el-descriptions-item label="បញ្ចូលក្របខ័ណ្ឌលេខ">{{ s.establishment_no }}</el-descriptions-item>
            <el-descriptions-item label="ប្រភេទសេវា">{{ s.service_track === 'combat' ? 'ប្រតិបត្តិការសឹក' : 'សេវារដ្ឋបាល' }}</el-descriptions-item>
            <el-descriptions-item label="ថ្ងៃឡើងស័ក្តិ">{{ fmtDate(s.rank_date) }}</el-descriptions-item>
            <el-descriptions-item label="ថ្ងៃមុខតំណែង">{{ fmtDate(s.position_date) }}</el-descriptions-item>
            <el-descriptions-item label="ថ្ងៃផ្លាស់ប្ដូរកងឯកភាព">{{ fmtDate(s.unit_transfer_date) }}</el-descriptions-item>
            <el-descriptions-item label="មកពីស្ថាប័នកងឯកភាព" :span="2">{{ s.from_unit_text }}</el-descriptions-item>
            <el-descriptions-item label="ប្រាក់បៀវត្សតាមឋានន្តរស័ក្តិ">{{ money(s.rank_salary) }}</el-descriptions-item>
            <el-descriptions-item label="ប្រាក់បៀវត្សមុខតំណែង" :span="2">{{ money(s.position_salary) }}</el-descriptions-item>
            <el-descriptions-item label="កម្រិតវប្បធម៌">{{ s.education_level_name }}</el-descriptions-item>
            <el-descriptions-item label="ជំនាញឯកទេស">{{ s.specialty_name }}</el-descriptions-item>
            <el-descriptions-item label="ប្រភេទឈាម">{{ s.blood_type_name }}</el-descriptions-item>
            <el-descriptions-item label="ឆ្លងប្រយុទ្ធ">{{ s.combat_veteran ? `បាទ/ចាស ${s.combat_note || ''}` : 'ទេ' }}</el-descriptions-item>
            <el-descriptions-item label="ភាសាបរទេស" :span="2">{{ s.languages.map((l) => `${l.language_name}${l.level ? ` (${l.level})` : ''}`).join(', ') }}</el-descriptions-item>
            <el-descriptions-item label="ស្ថានភាពគ្រួសារ">{{ s.marital_status_name }}</el-descriptions-item>
            <el-descriptions-item label="ប្ដី/ប្រពន្ធ">{{ s.spouse_name }}</el-descriptions-item>
            <el-descriptions-item label="មុខរបរ">{{ s.spouse_job_name }}</el-descriptions-item>
            <el-descriptions-item label="ចំនួនកូន">{{ num(s.children_count) }}</el-descriptions-item>
            <el-descriptions-item label="ឈ្មោះឪពុក">{{ s.father_name }}</el-descriptions-item>
            <el-descriptions-item label="ឈ្មោះម្ដាយ">{{ s.mother_name }}</el-descriptions-item>
            <el-descriptions-item label="ស្ថានភាពលំនៅ">{{ s.housing_status_name }}</el-descriptions-item>
            <el-descriptions-item label="អ្នកក្នុងបន្ទុក">{{ num(s.dependents_count) }}</el-descriptions-item>
            <el-descriptions-item label="ជួលមូលដ្ឋាន" :span="2">{{ s.base_village_text }}</el-descriptions-item>
            <el-descriptions-item label="ទីបោះឆ្នោត" :span="3">{{ [s.voting_place, s.voting_village_text].filter(Boolean).join(' — ') }}</el-descriptions-item>
            <el-descriptions-item label="ប្រវត្តិផ្សេងៗ" :span="3"><div style="white-space: pre-line">{{ s.notes }}</div></el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>

        <el-tab-pane :label="`ប្រវត្តិការងារ (${s.history.length})`" name="history">
          <el-timeline>
            <el-timeline-item v-for="h in s.history" :key="h.id" :timestamp="fmtDate(h.effective_date)" placement="top">
              <el-tag :type="KIND_TYPE[h.kind]" size="small">{{ KIND[h.kind] || h.kind }}</el-tag>
              <span class="muted"> {{ h.note }}</span>
              <div v-if="change(h.old_rank, h.new_rank)">ឋានន្តរស័ក្តិ៖ {{ change(h.old_rank, h.new_rank) }}</div>
              <div v-if="change(h.old_position, h.new_position)">មុខតំណែង៖ {{ change(h.old_position, h.new_position) }}</div>
              <div v-if="change(h.old_unit, h.new_unit)">អង្គភាព៖ {{ change(h.old_unit, h.new_unit) }}</div>
            </el-timeline-item>
          </el-timeline>
        </el-tab-pane>

        <el-tab-pane :label="`ការសិក្សា (${s.educations.length + s.trainings.length})`" name="edu">
          <div class="section-title">ប្រវត្តិសិក្សា</div>
          <el-table :data="s.educations" border size="small" empty-text="គ្មាន">
            <el-table-column label="ប្រភេទ" width="130"><template #default="{ row }">{{ EDU_KIND[row.kind] }}</template></el-table-column>
            <el-table-column prop="education_level_name" label="កម្រិត" width="130" />
            <el-table-column prop="specialty_text" label="ជំនាញ" />
            <el-table-column prop="institution" label="គ្រឹះស្ថាន" />
            <el-table-column label="ក្នុង/ក្រៅប្រទេស" width="120"><template #default="{ row }">{{ row.is_abroad ? 'ក្រៅប្រទេស' : 'ក្នុងប្រទេស' }}</template></el-table-column>
            <el-table-column label="រយៈពេល" width="200"><template #default="{ row }">{{ fmtDate(row.start_date) }} - {{ fmtDate(row.end_date) }} {{ row.duration_text }}</template></el-table-column>
          </el-table>
          <div class="section-title">វគ្គបណ្ដុះបណ្ដាល</div>
          <el-table :data="s.trainings" border size="small" empty-text="គ្មាន">
            <el-table-column prop="name" label="វគ្គ" />
            <el-table-column label="ប្រភេទ" width="120"><template #default="{ row }">{{ row.course_type === 'long' ? 'រយៈពេលវែង' : 'រយៈពេលខ្លី' }}</template></el-table-column>
            <el-table-column prop="institution" label="គ្រឹះស្ថាន" />
            <el-table-column label="រយៈពេល" width="200"><template #default="{ row }">{{ fmtDate(row.start_date) }} - {{ fmtDate(row.end_date) }}</template></el-table-column>
            <el-table-column prop="result" label="លទ្ធផល" width="120" />
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="`សរសើរ/វិន័យ (${s.awards.length + s.disciplines.length})`" name="awards">
          <div class="section-title">សរសើរ និងគ្រឿងឥស្សរិយយស</div>
          <el-table :data="s.awards" border size="small" empty-text="គ្មាន">
            <el-table-column prop="award_type_name" label="ប្រភេទ" width="180" />
            <el-table-column prop="decision_no" label="លេខលិខិត" width="130" />
            <el-table-column label="ថ្ងៃខែឆ្នាំ" width="120"><template #default="{ row }">{{ fmtDate(row.decision_date) }}</template></el-table-column>
            <el-table-column prop="reason" label="ខ្លឹមសារ" />
          </el-table>
          <div class="section-title">វិន័យ និងទណ្ឌកម្ម</div>
          <el-table :data="s.disciplines" border size="small" empty-text="គ្មាន">
            <el-table-column prop="discipline_type_name" label="ប្រភេទ" width="180" />
            <el-table-column prop="decision_no" label="លេខលិខិត" width="130" />
            <el-table-column label="រយៈពេល" width="210"><template #default="{ row }">{{ fmtDate(row.start_date) }} - {{ fmtDate(row.end_date) }}</template></el-table-column>
            <el-table-column prop="reason" label="មូលហេតុ" />
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="ឯកសារភ្ជាប់" name="files" lazy>
          <FileAttachments owner-type="soldier" :owner-id="s.id" :base-url="`/soldiers/${s.id}/attachments`"
                           :editable="auth.can('soldiers.update')" />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<style scoped>
.header { display: flex; gap: 20px; align-items: center; flex-wrap: wrap; }
.photo { width: 110px; height: 146px; border-radius: 6px; overflow: hidden; border: 1px solid #e1e6ea; }
.photo :deep(img) { width: 100%; height: 100%; object-fit: cover; }
.head-info { flex: 1; min-width: 280px; }
.name { font-size: 20px; margin-bottom: 8px; }
.chips { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
.quick { max-width: 800px; }
</style>
