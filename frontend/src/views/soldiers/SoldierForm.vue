<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http from '@/api/http'
import { useLookups } from '@/stores/lookups'
import UnitTreeSelect from '@/components/UnitTreeSelect.vue'
import VillageSelect from '@/components/VillageSelect.vue'
import AuthImage from '@/components/AuthImage.vue'

const route = useRoute()
const router = useRouter()
const lookups = useLookups()
const id = computed(() => (route.params.id ? Number(route.params.id) : null))
const formRef = ref()
const saving = ref(false)
const loading = ref(false)
const tab = ref('general')
const photoFile = ref(null)
const photoPreview = ref('')
const hasPhoto = ref(false)

const empty = () => ({
  military_id: '', name_kh: '', name_latin: '', gender: 'M', date_of_birth: null, national_id: '', phone: '',
  blood_type_id: null, birth_village_id: null, birth_place_text: '', current_village_id: null, current_address_text: '',
  current_rank_id: null, rank_date: null, current_position_id: null, position_date: null, current_unit_id: null,
  unit_transfer_date: null, from_unit_text: '', enlistment_date: null,
  status_id: lookups.list('soldier_status').find((s) => s.code === 'active')?.id ?? null,
  education_level_id: null, specialty_id: null, combat_veteran: false, combat_note: '',
  marital_status_id: null, spouse_name: '', spouse_job_id: null, children_count: 0, father_name: '', mother_name: '',
  notes: '', educations: [], languages: [], children: [],
})
const form = ref(empty())

const rules = {
  military_id: [{ required: true, message: 'សូមបញ្ចូលអត្តលេខ' }],
  name_kh: [{ required: true, message: 'សូមបញ្ចូលគោត្តនាមនិងនាម' }],
  gender: [{ required: true, message: 'សូមជ្រើសរើសភេទ' }],
}

const married = computed(() => {
  const status = lookups.list('marital_status').find((m) => m.id === form.value.marital_status_id)
  return !!status && status.code !== 'single'
})

onMounted(async () => {
  if (!id.value) return
  loading.value = true
  try {
    const { data } = await http.get(`/soldiers/${id.value}`)
    const f = empty()
    for (const k of Object.keys(f)) if (data[k] !== undefined) f[k] = data[k]
    f.educations = data.educations.map(({ id: _, soldier_id: __, created_at: ___, updated_at: ____, ...e }) => e)
    f.languages = data.languages.map(({ language_id, level }) => ({ language_id, level }))
    f.children = data.children.map(({ name, gender, date_of_birth }) => ({ name, gender, date_of_birth }))
    form.value = f
    hasPhoto.value = !!data.photo_path
  } finally {
    loading.value = false
  }
})

function pickPhoto(file) {
  photoFile.value = file.raw
  photoPreview.value = URL.createObjectURL(file.raw)
  return false
}

async function save() {
  try {
    await formRef.value.validate()
  } catch {
    tab.value = 'general'
    ElMessage.warning('សូមបំពេញព័ត៌មានដែលចាំបាច់')
    return
  }
  saving.value = true
  try {
    // rows left empty would fail validation on the server
    const payload = {
      ...form.value,
      languages: form.value.languages.filter((l) => l.language_id),
      children: form.value.children.filter((c) => c.name?.trim()),
    }
    const { data } = id.value
      ? await http.put(`/soldiers/${id.value}`, payload)
      : await http.post('/soldiers', payload)
    let photoFailed = false
    if (photoFile.value) {
      const fd = new FormData()
      fd.append('file', photoFile.value)
      // the soldier is saved already: a failed photo must not keep the user on the "new" form (saving again = duplicate)
      try { await http.post(`/soldiers/${data.id}/photo`, fd) } catch { photoFailed = true }
    }
    if (photoFailed) ElMessage.warning('បានរក្សាទុកព័ត៌មាន ប៉ុន្តែរូបថតមិនអាចផ្ទុកបាន')
    else ElMessage.success('បានរក្សាទុកដោយជោគជ័យ')
    router.push(`/soldiers/${data.id}`)
  } finally {
    saving.value = false
  }
}

const cambodiaId = computed(() => lookups.list('countries').find((c) => c.name_en === 'Cambodia')?.id ?? null)
const addEdu = () => form.value.educations.push({ kind: 'general', education_level_id: null, specialty_text: '', institution: '', country_id: cambodiaId.value, is_abroad: false, start_date: null, end_date: null, duration_text: '' })
const addLang = () => form.value.languages.push({ language_id: null, level: '' })
const addChild = () => form.value.children.push({ name: '', gender: null, date_of_birth: null })
</script>

<template>
  <div v-loading="loading" class="page">
    <div class="page-head">
      <h2>{{ id ? 'កែប្រែប្រវត្តិរូបយោធិន' : 'បញ្ចូលយោធិនថ្មី' }}</h2>
      <div class="head-actions">
        <el-button icon="Back" @click="router.back()">ត្រឡប់ក្រោយ</el-button>
        <el-button type="primary" icon="Check" :loading="saving" @click="save">រក្សាទុក</el-button>
      </div>
    </div>

    <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
      <el-card shadow="never">
        <el-tabs v-model="tab">
          <!-- ព័ត៌មានទូទៅ -->
          <el-tab-pane label="ព័ត៌មានទូទៅ" name="general">
            <div class="general">
              <div class="photo-box">
                <div class="photo">
                  <img v-if="photoPreview" :src="photoPreview" alt="" />
                  <AuthImage v-else-if="hasPhoto" :src="`/soldiers/${id}/photo`" />
                  <div v-else class="photo-empty"><el-icon :size="48"><UserFilled /></el-icon><small>៤x៦</small></div>
                </div>
                <el-upload :show-file-list="false" :auto-upload="false" accept=".jpg,.jpeg,.png,.webp" :on-change="pickPhoto">
                  <el-button size="small" icon="Camera">ជ្រើសរើសរូបថត</el-button>
                </el-upload>
              </div>
              <el-row :gutter="14" class="grow">
                <el-col :md="8"><el-form-item label="អត្តលេខ" prop="military_id"><el-input v-model="form.military_id" /></el-form-item></el-col>
                <el-col :md="8"><el-form-item label="គោត្តនាមនិងនាម" prop="name_kh"><el-input v-model="form.name_kh" /></el-form-item></el-col>
                <el-col :md="8"><el-form-item label="ឈ្មោះជាអក្សរឡាតាំង"><el-input v-model="form.name_latin" @input="(v) => (form.name_latin = v.toUpperCase())" /></el-form-item></el-col>
                <el-col :md="4"><el-form-item label="ភេទ" prop="gender">
                  <el-radio-group v-model="form.gender"><el-radio value="M">ប្រុស</el-radio><el-radio value="F">ស្រី</el-radio></el-radio-group>
                </el-form-item></el-col>
                <el-col :md="5"><el-form-item label="ថ្ងៃខែឆ្នាំកំណើត"><el-date-picker v-model="form.date_of_birth" value-format="YYYY-MM-DD" format="DD/MM/YYYY" style="width: 100%" /></el-form-item></el-col>
                <el-col :md="5"><el-form-item label="លេខអត្តសញ្ញាណប័ណ្ណសញ្ជាតិខ្មែរ"><el-input v-model="form.national_id" /></el-form-item></el-col>
                <el-col :md="5"><el-form-item label="លេខទូរសព្ទ"><el-input v-model="form.phone" /></el-form-item></el-col>
                <el-col :md="5"><el-form-item label="ប្រភេទឈាម">
                  <el-select v-model="form.blood_type_id" clearable><el-option v-for="o in lookups.list('blood_type')" :key="o.id" :value="o.id" :label="o.name_kh" /></el-select>
                </el-form-item></el-col>
              </el-row>
            </div>
            <div class="section-title">ទីកន្លែងកំណើត</div>
            <VillageSelect v-model="form.birth_village_id" />
            <el-form-item label="ឬ បញ្ចូលជាអក្សរ (ករណីមិនមានក្នុងបញ្ជី)" style="margin-top: 8px"><el-input v-model="form.birth_place_text" /></el-form-item>
            <div class="section-title">ទីលំនៅបច្ចុប្បន្ន</div>
            <VillageSelect v-model="form.current_village_id" />
            <el-form-item label="ផ្ទះលេខ ផ្លូវ ..." style="margin-top: 8px"><el-input v-model="form.current_address_text" /></el-form-item>
          </el-tab-pane>

          <!-- សេវាកម្ម -->
          <el-tab-pane label="ការងារ និងឋានន្តរស័ក្តិ" name="service">
            <el-alert v-if="id" type="info" show-icon :closable="false" style="margin-bottom: 14px"
                      title="ការផ្លាស់ប្ដូរឋានន្តរស័ក្តិ មុខតំណែង ឬអង្គភាព គួរធ្វើតាមរយៈម៉ឺនុយ 'តែងតាំង ផ្លាស់ប្ដូរ និងដំឡើងស័ក្តិ'។ ការកែនៅទីនេះ នឹងកត់ត្រាជា 'ការកែតម្រូវ' ហើយការប្ដូរអង្គភាព នឹងរាប់បញ្ចូលក្នុងការងារកើនថយ (ផ្លាស់ចេញ/ផ្លាស់ចូល)។" />
            <el-row :gutter="14">
              <el-col :md="8"><el-form-item label="ឋានន្តរស័ក្តិ">
                <el-select v-model="form.current_rank_id" clearable filterable>
                  <el-option-group v-for="c in lookups.list('rank_classes')" :key="c.id" :label="c.name_kh">
                    <el-option v-for="r in lookups.list('ranks').filter((x) => x.rank_class_id === c.id)" :key="r.id" :value="r.id" :label="r.name_kh" />
                  </el-option-group>
                </el-select>
              </el-form-item></el-col>
              <el-col :md="4"><el-form-item label="ថ្ងៃខែឆ្នាំឡើងស័ក្តិ"><el-date-picker v-model="form.rank_date" value-format="YYYY-MM-DD" format="DD/MM/YYYY" style="width: 100%" /></el-form-item></el-col>
              <el-col :md="8"><el-form-item label="មុខតំណែង">
                <el-select v-model="form.current_position_id" clearable filterable><el-option v-for="o in lookups.list('positions')" :key="o.id" :value="o.id" :label="o.name_kh" /></el-select>
              </el-form-item></el-col>
              <el-col :md="4"><el-form-item label="ថ្ងៃខែឆ្នាំមុខតំណែង"><el-date-picker v-model="form.position_date" value-format="YYYY-MM-DD" format="DD/MM/YYYY" style="width: 100%" /></el-form-item></el-col>
              <el-col :md="12"><el-form-item label="អង្គភាព / ស្ថាប័នកងឯកភាព"><UnitTreeSelect v-model="form.current_unit_id" /></el-form-item></el-col>
              <el-col :md="4"><el-form-item label="ថ្ងៃផ្លាស់ប្ដូរកងឯកភាព"><el-date-picker v-model="form.unit_transfer_date" value-format="YYYY-MM-DD" format="DD/MM/YYYY" style="width: 100%" /></el-form-item></el-col>
              <el-col :md="8"><el-form-item label="មកពីស្ថាប័នកងឯកភាព"><el-input v-model="form.from_unit_text" /></el-form-item></el-col>
              <el-col :md="6"><el-form-item label="ថ្ងៃខែឆ្នាំបម្រើចូលទ័ព"><el-date-picker v-model="form.enlistment_date" value-format="YYYY-MM-DD" format="DD/MM/YYYY" style="width: 100%" /></el-form-item></el-col>
              <el-col :md="6"><el-form-item label="ស្ថានភាព">
                <el-select v-model="form.status_id" clearable><el-option v-for="o in lookups.list('soldier_status')" :key="o.id" :value="o.id" :label="o.name_kh" /></el-select>
              </el-form-item></el-col>
              <el-col :md="4"><el-form-item label="ឆ្លងប្រយុទ្ធ"><el-switch v-model="form.combat_veteran" active-text="បាទ/ចាស" /></el-form-item></el-col>
              <el-col :md="8"><el-form-item label="ព័ត៌មានឆ្លងប្រយុទ្ធ"><el-input v-model="form.combat_note" :disabled="!form.combat_veteran" /></el-form-item></el-col>
            </el-row>
          </el-tab-pane>

          <!-- ការសិក្សា -->
          <el-tab-pane label="ការសិក្សា និងភាសា" name="education">
            <el-row :gutter="14">
              <el-col :md="8"><el-form-item label="កម្រិតវប្បធម៌">
                <el-select v-model="form.education_level_id" clearable><el-option v-for="o in lookups.list('education_level')" :key="o.id" :value="o.id" :label="o.name_kh" /></el-select>
              </el-form-item></el-col>
              <el-col :md="8"><el-form-item label="ជំនាញឯកទេស">
                <el-select v-model="form.specialty_id" clearable filterable><el-option v-for="o in lookups.list('specialties')" :key="o.id" :value="o.id" :label="o.name_kh" /></el-select>
              </el-form-item></el-col>
            </el-row>
            <div class="section-title">ប្រវត្តិសិក្សា (ក្នុង និងក្រៅប្រទេស)</div>
            <el-table :data="form.educations" border size="small" empty-text="មិនទាន់មាន">
              <el-table-column label="ប្រភេទ" width="140"><template #default="{ row }">
                <el-select v-model="row.kind"><el-option value="general" label="វប្បធម៌ទូទៅ" /><el-option value="specialty" label="ជំនាញឯកទេស" /><el-option value="other" label="ក្រៅពីជំនាញ" /></el-select>
              </template></el-table-column>
              <el-table-column label="កម្រិត" width="150"><template #default="{ row }">
                <el-select v-model="row.education_level_id" clearable><el-option v-for="o in lookups.list('education_level')" :key="o.id" :value="o.id" :label="o.name_kh" /></el-select>
              </template></el-table-column>
              <el-table-column label="ជំនាញ/មុខវិជ្ជា" min-width="150"><template #default="{ row }"><el-input v-model="row.specialty_text" /></template></el-table-column>
              <el-table-column label="គ្រឹះស្ថាន" min-width="150"><template #default="{ row }"><el-input v-model="row.institution" /></template></el-table-column>
              <el-table-column label="ប្រទេស" width="150"><template #default="{ row }">
                <el-select v-model="row.country_id" filterable clearable @change="(v) => (row.is_abroad = !!v && v !== cambodiaId)">
                  <el-option v-for="o in lookups.list('countries')" :key="o.id" :value="o.id" :label="o.name_kh" />
                </el-select>
              </template></el-table-column>
              <el-table-column label="ចាប់ពី" width="140"><template #default="{ row }"><el-date-picker v-model="row.start_date" value-format="YYYY-MM-DD" format="DD/MM/YYYY" style="width: 100%" /></template></el-table-column>
              <el-table-column label="ដល់" width="140"><template #default="{ row }"><el-date-picker v-model="row.end_date" value-format="YYYY-MM-DD" format="DD/MM/YYYY" style="width: 100%" /></template></el-table-column>
              <el-table-column label="រយៈពេល" width="110"><template #default="{ row }"><el-input v-model="row.duration_text" /></template></el-table-column>
              <el-table-column width="50"><template #default="{ $index }"><el-button link type="danger" icon="Delete" @click="form.educations.splice($index, 1)" /></template></el-table-column>
            </el-table>
            <el-button class="add-row" icon="Plus" size="small" @click="addEdu">បន្ថែមការសិក្សា</el-button>

            <div class="section-title">ភាសាបរទេស</div>
            <div v-for="(l, i) in form.languages" :key="i" class="inline-row">
              <el-select v-model="l.language_id" placeholder="ភាសា" style="width: 200px">
                <el-option v-for="o in lookups.list('language')" :key="o.id" :value="o.id" :label="o.name_kh" />
              </el-select>
              <el-select v-model="l.level" placeholder="កម្រិត" style="width: 160px" allow-create filterable>
                <el-option value="ល្អណាស់" /><el-option value="ល្អ" /><el-option value="មធ្យម" /><el-option value="ខ្សោយ" />
              </el-select>
              <el-button link type="danger" icon="Delete" @click="form.languages.splice(i, 1)" />
            </div>
            <el-button class="add-row" icon="Plus" size="small" @click="addLang">បន្ថែមភាសា</el-button>
          </el-tab-pane>

          <!-- គ្រួសារ -->
          <el-tab-pane label="ស្ថានភាពគ្រួសារ" name="family">
            <el-row :gutter="14">
              <el-col :md="6"><el-form-item label="ស្ថានភាពគ្រួសារ">
                <el-select v-model="form.marital_status_id" clearable><el-option v-for="o in lookups.list('marital_status')" :key="o.id" :value="o.id" :label="o.name_kh" /></el-select>
              </el-form-item></el-col>
              <el-col :md="8"><el-form-item label="ឈ្មោះប្ដី ឬប្រពន្ធ"><el-input v-model="form.spouse_name" :disabled="!married" /></el-form-item></el-col>
              <el-col :md="6"><el-form-item label="មុខរបរ">
                <el-select v-model="form.spouse_job_id" clearable :disabled="!married"><el-option v-for="o in lookups.list('occupation')" :key="o.id" :value="o.id" :label="o.name_kh" /></el-select>
              </el-form-item></el-col>
              <el-col :md="4"><el-form-item label="ចំនួនកូន"><el-input-number v-model="form.children_count" :min="0" style="width: 100%" /></el-form-item></el-col>
              <el-col :md="12"><el-form-item label="ឈ្មោះឪពុក"><el-input v-model="form.father_name" /></el-form-item></el-col>
              <el-col :md="12"><el-form-item label="ឈ្មោះម្ដាយ"><el-input v-model="form.mother_name" /></el-form-item></el-col>
            </el-row>
            <div class="section-title">ព័ត៌មានកូន (ស្រេចចិត្ត)</div>
            <div v-for="(c, i) in form.children" :key="i" class="inline-row">
              <el-input v-model="c.name" placeholder="ឈ្មោះ" style="width: 240px" />
              <el-select v-model="c.gender" placeholder="ភេទ" style="width: 110px"><el-option value="M" label="ប្រុស" /><el-option value="F" label="ស្រី" /></el-select>
              <el-date-picker v-model="c.date_of_birth" value-format="YYYY-MM-DD" format="DD/MM/YYYY" placeholder="ថ្ងៃកំណើត" />
              <el-button link type="danger" icon="Delete" @click="form.children.splice(i, 1)" />
            </div>
            <el-button class="add-row" icon="Plus" size="small" @click="addChild">បន្ថែមកូន</el-button>
          </el-tab-pane>

          <el-tab-pane label="ប្រវត្តិផ្សេងៗ" name="notes">
            <el-form-item label="បន្ថែមប្រវត្តិផ្សេងៗ"><el-input v-model="form.notes" type="textarea" :rows="8" /></el-form-item>
            <p class="muted">ឯកសារភ្ជាប់ អាចបន្ថែមបាននៅទំព័រព័ត៌មានលម្អិតរបស់យោធិន បន្ទាប់ពីរក្សាទុក។</p>
          </el-tab-pane>
        </el-tabs>
      </el-card>
    </el-form>
  </div>
</template>

<style scoped>
.general { display: flex; gap: 20px; align-items: flex-start; }
.grow { flex: 1; }
.photo-box { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.photo { width: 120px; height: 160px; border: 1px dashed #c8d0d6; border-radius: 6px; overflow: hidden; background: #f7f9fa; }
.photo img, .photo :deep(img) { width: 100%; height: 100%; object-fit: cover; }
.photo-empty { height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #a0aab4; }
.inline-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
.add-row { margin-top: 8px; }
.el-select { width: 100%; }
@media (max-width: 900px) { .general { flex-direction: column; } }
</style>
