/** Field / column definitions for the conscription pages (យុវជនបំពេញកាតព្វកិច្ចយោធា). */
import { fmtDate } from '@/utils/format'

const GENDER = [{ value: 'M', label: 'ប្រុស' }, { value: 'F', label: 'ស្រី' }]
const year = (key, label, extra = {}) => ({ key, label, type: 'number', min: 1990, max: 2100, ...extra })

// meta: { statuses, reasons, results } from GET /meta/conscription; provinces / districts: [{ value, label }]
export function conscriptConfig(meta, provinces) {
  return {
    title: 'យុវជនបំពេញកាតព្វកិច្ចយោធា', endpoint: '/conscripts', module: 'conscripts', formWidth: '980px',
    attachments: 'conscript', attachmentTitle: 'conscript_no', actionWidth: 190,
    columns: [
      { key: 'conscript_no', label: 'លេខសម្គាល់', width: 130 },
      { key: 'name_kh', label: 'គោត្តនាម និងនាម', minWidth: 150 },
      { key: 'name_latin', label: 'ឈ្មោះឡាតាំង', minWidth: 140 },
      { key: 'gender', label: 'ភេទ', width: 70, value: (r) => (r.gender === 'M' ? 'ប្រុស' : 'ស្រី') },
      { key: 'date_of_birth', label: 'ថ្ងៃខែឆ្នាំកំណើត', type: 'date', width: 120 },
      { key: 'age', label: 'អាយុ', width: 70 },
      { key: 'national_id', label: 'លេខអត្តសញ្ញាណប័ណ្ណ', width: 140 },
      { key: 'rank_name', label: 'ឋានន្តរស័ក្តិ', width: 120 },
      { key: 'role', label: 'មុខតំណែង/តួនាទី', width: 130 },
      { key: 'unit_name', label: 'អង្គភាព', minWidth: 150 },
      { key: 'service_start', label: 'ថ្ងៃចូលបំពេញកាតព្វកិច្ច', type: 'date', width: 150 },
      { key: 'registration_year', label: 'ឆ្នាំចុះឈ្មោះ', width: 110 },
      { key: 'province_name', label: 'ខេត្តចុះឈ្មោះ', width: 130 },
      { key: 'status_name', label: 'ស្ថានភាព', width: 140, tag: (r) => STATUS_TAG[r.status] || 'info' },
    ],
    filters: [
      { key: 'status', label: 'ស្ថានភាព', type: 'select', width: '160px', options: meta.statuses },
      year('registration_year', 'ឆ្នាំ', { width: '130px' }),
      { key: 'province_id', label: 'ខេត្ត', type: 'select', width: '170px', options: provinces },
      { key: 'gender', label: 'ភេទ', type: 'select', width: '100px', options: GENDER },
      { key: 'unit_id', label: 'អង្គភាព', type: 'unit', width: '220px' },
      { key: 'rank_id', label: 'ឋានន្តរស័ក្តិ', type: 'select', width: '160px', options: (row, lk) => lk.list('ranks').map((r) => ({ value: r.id, label: r.name_kh })) },
      { key: 'education_level_id', label: 'កម្រិតវប្បធម៌', type: 'select', width: '150px', options: 'lookup:education_level' },
      { key: 'section_id', label: 'ផ្នែក', type: 'select', width: '170px', options: 'lookup:specialty_section' },
      { key: 'specialty_id', label: 'ជំនាញ', type: 'select', width: '170px', options: 'specialties' },
      { key: 'blood_type_id', label: 'ប្រភេទឈាម', type: 'select', width: '110px', options: 'lookup:blood_type' },
      { key: 'marital_status_id', label: 'ស្ថានភាពគ្រួសារ', type: 'select', width: '140px', options: 'lookup:marital_status' },
      { key: 'age_min', label: 'អាយុពី', type: 'number', width: '110px' },
      { key: 'age_max', label: 'ដល់', type: 'number', width: '110px' },
    ],
    fields: [
      { key: 'conscript_no', label: 'លេខសម្គាល់យោធា / លេខសម្គាល់ខ្លួន', required: true, span: 8 },
      { key: 'name_kh', label: 'គោត្តនាម និងនាម', required: true, span: 8 },
      { key: 'name_latin', label: 'ឈ្មោះឡាតាំង', span: 8 },
      { key: 'gender', label: 'ភេទ', type: 'select', required: true, default: 'M', options: GENDER, span: 4 },
      { key: 'date_of_birth', label: 'ថ្ងៃខែឆ្នាំកំណើត', type: 'date', span: 5 },
      { key: 'nationality', label: 'សញ្ជាតិ', default: 'ខ្មែរ', span: 5 },
      { key: 'national_id', label: 'លេខអត្តសញ្ញាណប័ណ្ណ', span: 5 },
      { key: 'phone', label: 'លេខទូរសព្ទ', span: 5 },
      { key: 'birth_village_id', label: 'ទីកន្លែងកំណើត', type: 'village' },
      { key: 'birth_place_text', label: 'ទីកន្លែងកំណើត (ជាអក្សរ ករណីមិនមានក្នុងបញ្ជី)' },
      { key: 'current_village_id', label: 'អាសយដ្ឋានបច្ចុប្បន្ន (ភូមិ ឃុំ ស្រុក ខេត្ត)', type: 'village' },
      { key: 'current_address_text', label: 'ផ្ទះលេខ ផ្លូវ' },
      { key: 'father_name', label: 'ឈ្មោះឪពុក', span: 12 },
      { key: 'mother_name', label: 'ឈ្មោះម្ដាយ', span: 12 },
      { key: 'marital_status_id', label: 'ស្ថានភាពគ្រួសារ', type: 'select', options: 'lookup:marital_status', span: 8 },
      { key: 'spouse_name', label: 'ឈ្មោះប្ដី/ប្រពន្ធ', span: 8 },
      { key: 'spouse_job_id', label: 'មុខរបរប្ដី/ប្រពន្ធ', type: 'select', options: 'lookup:occupation', span: 4 },
      { key: 'children_count', label: 'ចំនួនកូន', type: 'number', default: 0, span: 4 },
      { key: 'education_level_id', label: 'កម្រិតវប្បធម៌', type: 'select', options: 'lookup:education_level', span: 6 },
      { key: 'specialty_id', label: 'ជំនាញឯកទេស', type: 'select', options: 'specialties', span: 6 },
      { key: 'blood_type_id', label: 'ប្រភេទឈាម', type: 'select', options: 'lookup:blood_type', span: 4 },
      { key: 'profession', label: 'វិជ្ជាជីវៈ', span: 8 },
      { key: 'languages', label: 'ភាសាដែលចេះ', span: 6 },
      { key: 'driving_license', label: 'ប័ណ្ណបើកបរ (ប្រភេទ)', span: 6 },
      { key: 'notes', label: 'កំណត់សម្គាល់', type: 'textarea', rows: 2 },
    ],
  }
}

export const STATUS_TAG = { registered: 'info', called: 'warning', served: 'success', exempted: 'danger', deferred: '' }

export function registrationConfig(meta, provinces, districts, conscriptId) {
  return {
    title: 'ការចុះឈ្មោះកាតព្វកិច្ច', endpoint: '/conscript-registrations', module: 'conscripts', formWidth: '760px',
    fixedParams: { conscript_id: conscriptId },
    columns: [
      { key: 'registration_year', label: 'ឆ្នាំចុះឈ្មោះ', width: 110 },
      { key: 'duty_year', label: 'ឆ្នាំកាតព្វកិច្ច', width: 110 },
      { key: 'register_no', label: 'លេខបញ្ជីកាតព្វកិច្ច', width: 150 },
      { key: 'place', label: 'ទីតាំងចុះឈ្មោះ', minWidth: 180, value: (r) => [r.district_name, r.province_name].filter(Boolean).join(', ') },
      { key: 'status_name', label: 'ស្ថានភាព', width: 140, tag: (r) => STATUS_TAG[r.status] || 'info' },
      { key: 'reason', label: 'មូលហេតុ', minWidth: 160, value: (r) => [r.reason_name, r.reason_note].filter(Boolean).join(' — ') },
    ],
    fields: [
      year('registration_year', 'ឆ្នាំចុះឈ្មោះ', { required: true, default: new Date().getFullYear(), span: 8 }),
      year('duty_year', 'ឆ្នាំកាតព្វកិច្ច', { span: 8 }),
      { key: 'register_no', label: 'លេខសម្គាល់បញ្ជីកាតព្វកិច្ច', span: 8 },
      { key: 'province_id', label: 'រាជធានី/ខេត្ត', type: 'select', options: provinces, span: 12 },
      { key: 'district_id', label: 'ស្រុក/ខណ្ឌ', type: 'select', options: districts, span: 12 },
      { key: 'status', label: 'ស្ថានភាព', type: 'select', required: true, default: 'registered', options: meta.statuses, span: 12 },
      { key: 'reason', label: 'មូលហេតុនៃការលើកលែង ឬពន្យារ', type: 'select', options: meta.reasons, span: 12,
        showIf: (f) => ['exempted', 'deferred'].includes(f.status) },
      { key: 'reason_note', label: 'ព័ត៌មានបន្ថែមអំពីមូលហេតុ', type: 'textarea', rows: 2, showIf: (f) => ['exempted', 'deferred'].includes(f.status) },
    ],
  }
}

export function medicalConfig(meta, conscriptId) {
  return {
    title: 'ការពិនិត្យសុខភាព និងសមត្ថភាព', endpoint: '/conscript-medicals', module: 'conscript_medical', formWidth: '640px',
    fixedParams: { conscript_id: conscriptId },
    columns: [
      { key: 'exam_date', label: 'ថ្ងៃពិនិត្យ', type: 'date', width: 120 },
      { key: 'height_cm', label: 'កម្ពស់ (cm)', width: 110 },
      { key: 'weight_kg', label: 'ទម្ងន់ (kg)', width: 110 },
      { key: 'bmi', label: 'BMI', width: 80 },
      { key: 'result_name', label: 'លទ្ធផល', width: 110, tag: (r) => ({ pass: 'success', fail: 'danger', deferred: 'warning' })[r.result] },
      { key: 'examiner', label: 'មន្ត្រីពិនិត្យ', minWidth: 150 },
    ],
    fields: [
      { key: 'exam_date', label: 'កាលបរិច្ឆេទពិនិត្យ', type: 'date', required: true, span: 8 },
      { key: 'height_cm', label: 'កម្ពស់ (cm)', type: 'number', span: 8 },
      { key: 'weight_kg', label: 'ទម្ងន់ (kg)', type: 'number', span: 8 },
      { key: 'result', label: 'លទ្ធផល', type: 'select', required: true, options: meta.results, span: 12 },
      { key: 'examiner', label: 'មន្ត្រីពិនិត្យ', span: 12 },
      { key: 'notes', label: 'កំណត់សម្គាល់', type: 'textarea', rows: 2 },
    ],
  }
}

export function serviceConfig(conscriptId) {
  const ranks = (row, lk) => lk.list('ranks').map((r) => ({ value: r.id, label: r.name_kh }))
  return {
    title: 'ការបម្រើកាតព្វកិច្ច', endpoint: '/conscript-services', module: 'conscripts', formWidth: '820px',
    fixedParams: { conscript_id: conscriptId },
    columns: [
      { key: 'period', label: 'រយៈពេល', width: 210, value: (r) => `${fmtDate(r.start_date)} – ${fmtDate(r.end_date) || '...'}` },
      { key: 'unit_name', label: 'អង្គភាព/កងពល/កងវរសេនាធំ', minWidth: 180 },
      { key: 'rank_name', label: 'ឋានន្តរស័ក្តិ', width: 130 },
      { key: 'role', label: 'តួនាទី', width: 130 },
      { key: 'order_no', label: 'លេខបញ្ជា/សេចក្ដីសម្រេច', width: 160 },
    ],
    fields: [
      { key: 'start_date', label: 'ថ្ងៃចូលបម្រើ', type: 'date', span: 8 },
      { key: 'end_date', label: 'ថ្ងៃចេញ', type: 'date', span: 8 },
      { key: 'order_no', label: 'លេខបញ្ជា/សេចក្ដីសម្រេច', span: 8 },
      { key: 'unit_id', label: 'អង្គភាព', type: 'unit', span: 12 },
      { key: 'unit_text', label: 'ឬ អង្គភាព/កងពល/កងវរសេនាធំ (ជាអក្សរ)', span: 12 },
      { key: 'rank_id', label: 'ឋានន្តរស័ក្តិ', type: 'select', options: ranks, span: 12 },
      { key: 'role', label: 'តួនាទី', span: 12 },
      { key: 'trainings', label: 'វគ្គបណ្ដុះបណ្ដាលដែលបានចូលរួម', type: 'textarea', rows: 2 },
      { key: 'awards_discipline', label: 'ការលើកសរសើរ / វិន័យ', type: 'textarea', rows: 2 },
    ],
  }
}
