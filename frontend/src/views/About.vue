<script setup>
/** អំពីយើង (New (2).txt §13): system version, contact (ទំនាក់ទំនង), user guide (សៀវភៅណែនាំ), change history (ប្រវត្តិកែប្រែ). */
import { computed, onMounted, ref } from 'vue'
import axios from 'axios'
import http from '@/api/http'
import { useAuth } from '@/stores/auth'
import BrandLogo from '@/components/BrandLogo.vue'
import { CHANGELOG, GUIDE } from '@/about-content'
import { fmtDate } from '@/utils/format'

/* global __APP_VERSION__ */
const appVersion = __APP_VERSION__
const auth = useAuth()
const settings = ref({})
const apiVersion = ref('')
const openGuide = ref([0])

const value = (key) => settings.value[key]?.value?.trim() || ''
// ទំនាក់ទំនង: set under ការកំណត់ → ការកំណត់ប្រព័ន្ធ
const contacts = computed(() => [
  ['អង្គភាព/អ្នកទទួលបន្ទុក', value('contact_name')],
  ['ទូរស័ព្ទ', value('contact_phone')],
  ['អ៊ីមែល', value('contact_email')],
  ['អាសយដ្ឋាន', value('contact_address')],
].filter(([, v]) => v))
const manualUrl = computed(() => value('manual_url'))
const isLink = (v) => /^https?:\/\//i.test(v)

onMounted(async () => {
  settings.value = (await http.get('/settings')).data
  try { apiVersion.value = (await axios.get('/api/health')).data.version || '' } catch { /* API version is optional */ }
})
</script>

<template>
  <div class="page">
    <div class="page-head"><h2>អំពីយើង</h2></div>
    <el-card shadow="never">
      <div class="about">
        <BrandLogo class="logo" />
        <div class="grow">
          <h3 class="moul">ប្រព័ន្ធគ្រប់គ្រងយោធិន</h3>
          <p>{{ value('org_name_kh') }}</p>
          <p class="muted">{{ value('org_name_en') }}</p>
          <p>
            ប្រព័ន្ធនេះប្រើសម្រាប់គ្រប់គ្រងប្រវត្តិរូបយោធិន ឯកសារចេញចូល ការតែងតាំង ផ្លាស់ប្ដូរ និងដំឡើងឋានន្តរស័ក្តិ
            ការបណ្ដុះបណ្ដាល វិន័យ ការសរសើរ ប័ណ្ណយោធិន សោធននិវត្តន៍ គោលនយោបាយ យោធិនចេញពីជួរ និងរបាយការណ៍។
          </p>
          <el-descriptions :column="1" border size="small" class="facts">
            <el-descriptions-item label="ជំនាន់ប្រព័ន្ធ">{{ appVersion }}<span v-if="apiVersion && apiVersion !== appVersion" class="muted"> (API {{ apiVersion }})</span></el-descriptions-item>
            <el-descriptions-item label="ធ្វើបច្ចុប្បន្នភាពចុងក្រោយ">{{ fmtDate(CHANGELOG[0].date) }}</el-descriptions-item>
            <el-descriptions-item label="Backend">Python · FastAPI · SQLAlchemy</el-descriptions-item>
            <el-descriptions-item label="Frontend">Vue 3 · Element Plus</el-descriptions-item>
            <el-descriptions-item label="Database">MySQL / PostgreSQL</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" header="ទំនាក់ទំនង">
      <el-descriptions v-if="contacts.length" :column="1" border size="small" class="facts">
        <el-descriptions-item v-for="[label, v] in contacts" :key="label" :label="label">
          <a v-if="label === 'អ៊ីមែល'" :href="`mailto:${v}`">{{ v }}</a>
          <a v-else-if="label === 'ទូរស័ព្ទ'" :href="`tel:${v.replace(/\s/g, '')}`">{{ v }}</a>
          <span v-else>{{ v }}</span>
        </el-descriptions-item>
      </el-descriptions>
      <p v-else class="muted">
        មិនទាន់បានកំណត់ព័ត៌មានទំនាក់ទំនង។
        <router-link v-if="auth.can('settings.update')" to="/settings/system">កំណត់នៅ ការកំណត់ → ការកំណត់ប្រព័ន្ធ</router-link>
      </p>
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="card-head">
          <span>សៀវភៅណែនាំ</span>
          <el-button v-if="manualUrl && isLink(manualUrl)" size="small" icon="Download" tag="a" :href="manualUrl" target="_blank" rel="noopener">
            សៀវភៅណែនាំពេញលេញ
          </el-button>
        </div>
      </template>
      <el-collapse v-model="openGuide">
        <el-collapse-item v-for="(g, i) in GUIDE" :key="g.title" :name="i" :title="`${i + 1}. ${g.title}`">
          <ol class="steps"><li v-for="s in g.steps" :key="s">{{ s }}</li></ol>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <el-card shadow="never" header="ប្រវត្តិកែប្រែ">
      <el-timeline>
        <el-timeline-item v-for="(r, i) in CHANGELOG" :key="r.version" :timestamp="fmtDate(r.date)" placement="top"
                          :type="i === 0 ? 'primary' : ''">
          <b>ជំនាន់ {{ r.version }}</b>
          <ul class="steps"><li v-for="c in r.changes" :key="c">{{ c }}</li></ul>
        </el-timeline-item>
      </el-timeline>
    </el-card>
  </div>
</template>

<style scoped>
.about { display: flex; gap: 24px; align-items: flex-start; flex-wrap: wrap; }
.logo { width: 96px; height: 96px; object-fit: contain; }
.grow { flex: 1; min-width: 0; }
.facts { max-width: 520px; }
h3 { color: var(--brand); margin-top: 0; line-height: 1.8; }
p { line-height: 1.9; max-width: 720px; }
.card-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.steps { margin: 4px 0; padding-left: 22px; line-height: 1.9; }
</style>
