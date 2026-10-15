<script setup>
/** One conscript: personal details and photo, registrations, medical exams (own permission), service, attachments. */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http from '@/api/http'
import { useAuth } from '@/stores/auth'
import { useLookups } from '@/stores/lookups'
import AuthImage from '@/components/AuthImage.vue'
import CrudPage from '@/components/CrudPage.vue'
import FileAttachments from '@/components/FileAttachments.vue'
import { medicalConfig, registrationConfig, serviceConfig, STATUS_TAG } from '@/conscript-configs'
import { fmtDate, genderText, num } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const auth = useAuth()
const lookups = useLookups()
const id = Number(route.params.id)
const c = ref(null)
const meta = ref(null)
const provinces = ref([])
const districts = ref([])
const tab = ref('registrations')
const photoKey = ref(0)
const places = ref({})

async function loadPerson() {
  c.value = (await http.get(`/conscripts/${id}`)).data
  for (const key of ['birth_village_id', 'current_village_id']) {
    const vid = c.value[key]
    places.value[key] = vid ? (await http.get(`/geo/village-path/${vid}`, { silent: true })).data.text : ''
  }
}

onMounted(async () => {
  const [m, p, d] = await Promise.all([
    http.get('/meta/conscription'), http.get('/geo/provinces', { params: { size: 100 } }),
    http.get('/geo/districts', { params: { size: 1000 } }),
  ])
  meta.value = m.data
  const provName = Object.fromEntries(p.data.items.map((x) => [x.id, `${x.type}${x.name_kh}`]))
  provinces.value = p.data.items.map((x) => ({ value: x.id, label: provName[x.id] }))
  districts.value = d.data.items.map((x) => ({ value: x.id, label: `${x.type}${x.name_kh} (${provName[x.province_id]})` }))
  await loadPerson()
})

async function uploadPhoto({ file }) {
  const fd = new FormData()
  fd.append('file', file)
  await http.post(`/conscripts/${id}/photo`, fd)
  ElMessage.success('បានផ្លាស់ប្ដូររូបថត')
  await loadPerson()
  photoKey.value++
}

const canMedical = computed(() => auth.can('conscript_medical.view'))
</script>

<template>
  <div v-if="c && meta" class="page">
    <div class="page-head">
      <h2>យុវជនបំពេញកាតព្វកិច្ចយោធា</h2>
      <div class="head-actions"><el-button icon="Back" @click="router.push('/conscripts')">បញ្ជី</el-button></div>
    </div>

    <el-card shadow="never">
      <div class="header">
        <div class="photo-box">
          <div class="photo"><AuthImage :key="photoKey" :src="c.photo_path ? `/conscripts/${id}/photo` : ''" /></div>
          <el-upload v-if="auth.can('conscripts.update')" :show-file-list="false" accept=".jpg,.jpeg,.png,.webp" :http-request="uploadPhoto">
            <el-button size="small" icon="Camera">រូបថត</el-button>
          </el-upload>
        </div>
        <div class="grow">
          <div class="name"><b>{{ c.name_kh }}</b> <span class="muted">{{ c.name_latin }}</span></div>
          <div class="chips">
            <el-tag>លេខសម្គាល់ {{ c.conscript_no }}</el-tag>
            <el-tag v-if="c.status_name" :type="STATUS_TAG[c.status] || 'info'">{{ c.status_name }} {{ num(c.registration_year) }}</el-tag>
          </div>
          <el-descriptions :column="3" size="small" border>
            <el-descriptions-item label="ភេទ">{{ genderText(c.gender) }}</el-descriptions-item>
            <el-descriptions-item label="ថ្ងៃខែឆ្នាំកំណើត">{{ fmtDate(c.date_of_birth) }} <span v-if="c.age != null">({{ num(c.age) }} ឆ្នាំ)</span></el-descriptions-item>
            <el-descriptions-item label="សញ្ជាតិ">{{ c.nationality }}</el-descriptions-item>
            <el-descriptions-item label="អត្តសញ្ញាណប័ណ្ណ">{{ c.national_id }}</el-descriptions-item>
            <el-descriptions-item label="ទូរសព្ទ">{{ c.phone }}</el-descriptions-item>
            <el-descriptions-item label="កម្រិតវប្បធម៌">{{ c.education_level_name }}</el-descriptions-item>
            <el-descriptions-item label="ទីកន្លែងកំណើត" :span="3">{{ places.birth_village_id || c.birth_place_text }}</el-descriptions-item>
            <el-descriptions-item label="អាសយដ្ឋានបច្ចុប្បន្ន" :span="3">{{ [c.current_address_text, places.current_village_id].filter(Boolean).join(' ') }}</el-descriptions-item>
            <el-descriptions-item label="ឪពុក">{{ c.father_name }}</el-descriptions-item>
            <el-descriptions-item label="ម្ដាយ">{{ c.mother_name }}</el-descriptions-item>
            <el-descriptions-item label="ស្ថានភាពគ្រួសារ">{{ lookups.name('marital_status', c.marital_status_id) }}
              <span v-if="c.spouse_name">— {{ c.spouse_name }}</span><span v-if="c.children_count">, កូន {{ num(c.children_count) }}</span></el-descriptions-item>
            <el-descriptions-item label="ជំនាញ/វិជ្ជាជីវៈ">{{ c.profession }}</el-descriptions-item>
            <el-descriptions-item label="ភាសា">{{ c.languages }}</el-descriptions-item>
            <el-descriptions-item label="ប័ណ្ណបើកបរ">{{ c.driving_license }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-tabs v-model="tab">
        <el-tab-pane label="ការចុះឈ្មោះកាតព្វកិច្ច" name="registrations">
          <CrudPage :config="registrationConfig(meta, provinces, districts, id)" @saved="loadPerson" />
        </el-tab-pane>
        <el-tab-pane v-if="canMedical" label="ការពិនិត្យសុខភាព" name="medical" lazy>
          <CrudPage :config="medicalConfig(meta, id)" />
        </el-tab-pane>
        <el-tab-pane label="ការបម្រើកាតព្វកិច្ច" name="service" lazy>
          <CrudPage :config="serviceConfig(id)" />
        </el-tab-pane>
        <el-tab-pane label="ឯកសារភ្ជាប់ (ស្កេនប្រវត្តិរូប)" name="files" lazy>
          <FileAttachments owner-type="conscript" :owner-id="id" :editable="auth.can('conscripts.update')" />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<style scoped>
.header { display: flex; gap: 20px; align-items: flex-start; }
.grow { flex: 1; min-width: 0; }
.photo-box { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.photo { width: 120px; height: 160px; border: 1px solid #dfe4e8; border-radius: 6px; overflow: hidden; background: #f7f9fa; }
.photo :deep(img) { width: 100%; height: 100%; object-fit: cover; }
.name { font-size: 20px; margin-bottom: 8px; }
.chips { display: flex; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; }
.page :deep(.el-tab-pane .page) { padding: 0; }
@media (max-width: 900px) { .header { flex-direction: column; } }
</style>
