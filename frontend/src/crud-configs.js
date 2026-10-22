/** Field / column definitions for the config-driven CRUD pages. */

const nameFields = [
  { key: 'name_kh', label: 'ឈ្មោះ (ខ្មែរ)', required: true, span: 12 },
  { key: 'name_en', label: 'ឈ្មោះ (អង់គ្លេស)', span: 12 },
]
const activeField = { key: 'active', label: 'សកម្ម', type: 'switch', default: true, span: 6 }
const nameCols = [
  { key: 'name_kh', label: 'ឈ្មោះ (ខ្មែរ)', minWidth: 200 },
  { key: 'name_en', label: 'ឈ្មោះ (អង់គ្លេស)', minWidth: 160 },
]
const activeCol = { key: 'active', label: 'ស្ថានភាព', width: 100, value: (r) => (r.active ? 'សកម្ម' : 'អសកម្ម'), tag: (r) => (r.active ? 'success' : 'info') }
const soldierCols = [
  { key: 'military_id', label: 'អត្តលេខ', width: 110 },
  { key: 'rank_name', label: 'ឋានន្តរស័ក្តិ', width: 130 },
  { key: 'soldier_name', label: 'គោត្តនាមនិងនាម', minWidth: 150 },
  { key: 'unit_name', label: 'អង្គភាព', minWidth: 150 },
]
const soldierField = { key: 'soldier_id', label: 'យោធិន', type: 'soldier', required: true }
const RETIREMENT_TYPES = [{ value: 'pension', label: 'សោធននិវត្តន៍ (គ្រប់អាយុ)' },
  { value: 'voluntary', label: 'ស្ម័គ្រចិត្តចូលនិវត្តន៍' }, { value: 'category2', label: 'យោធិនប្រភេទ២' }]
const POSITION_LEVELS = [{ value: 1, label: 'មុខតំណែង' }, { value: 2, label: 'មុខតំណែងរង' }, { value: 3, label: 'មុខតំណែងចំណុះផ្ទាល់' }]
// a position can sit under a level-1 or level-2 position, never under itself
const parentPositions = (row, lk) => lk.list('positions')
  .filter((p) => (p.level || 1) < 3 && p.id !== row.id)
  .map((p) => ({ value: p.id, label: `${'— '.repeat((p.level || 1) - 1)}${p.name_kh}` }))
const SPECIALTY_CATEGORY = { military: 'ជំនាញយោធា', civil: 'ជំនាញស៊ីវិល' }
const specialtyCategoryOptions = Object.entries(SPECIALTY_CATEGORY).map(([value, label]) => ({ value, label }))
const dateRange = [
  { key: 'date_from', label: 'ចាប់ពី', type: 'date', width: '150px' },
  { key: 'date_to', label: 'ដល់', type: 'date', width: '150px' },
]

export const configs = {
  positions: {
    title: 'មុខតំណែង', endpoint: '/positions', module: 'positions', refreshLookups: true, formWidth: '720px',
    columns: [...nameCols,
      { key: 'level_name', label: 'ថ្នាក់', width: 170, tag: (r) => ['', 'danger', 'warning', 'info'][r.level] },
      { key: 'parent_name', label: 'ចំណុះមុខតំណែង', minWidth: 160 },
      { key: 'grade', label: 'កម្រិត', width: 90 },
      { key: 'salary', label: 'ប្រាក់បៀវត្សមុខតំណែង', width: 170, value: (r) => (r.salary == null ? '' : Number(r.salary).toLocaleString('en-US')) },
      { key: 'sort_order', label: 'លំដាប់', width: 90 }, activeCol],
    filters: [{ key: 'level', label: 'ថ្នាក់', type: 'select', width: '200px', options: POSITION_LEVELS }],
    fields: [...nameFields,
      { key: 'parent_id', label: 'ចំណុះមុខតំណែង (ទុកទំនេរ = មុខតំណែងថ្នាក់ទី១)', type: 'select', options: parentPositions },
      { key: 'grade', label: 'កម្រិត', type: 'number', span: 6 },
      { key: 'salary', label: 'ប្រាក់បៀវត្សមុខតំណែង (រៀល)', type: 'number', span: 8 },
      { key: 'sort_order', label: 'លំដាប់', type: 'number', default: 0, span: 5 }, { ...activeField, span: 5 }],
  },
  specialties: {
    title: 'ជំនាញឯកទេស', endpoint: '/specialties', module: 'specialties', refreshLookups: true,
    columns: [...nameCols, { key: 'category', label: 'វិស័យ', width: 120, value: (r) => SPECIALTY_CATEGORY[r.category] },
      { key: 'section_name', label: 'ផ្នែក', minWidth: 170 }, activeCol],
    filters: [{ key: 'category', label: 'វិស័យ', type: 'select', width: '150px', options: specialtyCategoryOptions },
      { key: 'section_id', label: 'ផ្នែក', type: 'select', width: '200px', options: 'lookup:specialty_section' }],
    fields: [...nameFields, { key: 'category', label: 'វិស័យ (យោធា / ស៊ីវិល)', type: 'select', required: true, default: 'military', span: 8, options: specialtyCategoryOptions },
      { key: 'section_id', label: 'ផ្នែក', type: 'select', options: 'lookup:specialty_section', span: 10 },
      { ...activeField, span: 6 }],
  },
  documentTypes: {
    title: 'ប្រភេទឯកសារ', endpoint: '/document-types', module: 'doc_types', refreshLookups: true,
    columns: [...nameCols, { key: 'direction', label: 'ប្រើសម្រាប់', width: 140, value: (r) => ({ in: 'ឯកសារចូល', out: 'ឯកសារចេញ', both: 'ចូល និងចេញ' })[r.direction] }, activeCol],
    fields: [...nameFields, {
      key: 'direction', label: 'ប្រើសម្រាប់', type: 'select', default: 'both', span: 12,
      options: [{ value: 'both', label: 'ចូល និងចេញ' }, { value: 'in', label: 'ឯកសារចូល' }, { value: 'out', label: 'ឯកសារចេញ' }],
    }, { ...activeField, span: 12 }],
  },
  docIn: {
    title: 'ឯកសារចូល', endpoint: '/documents/incoming', module: 'doc_in', attachments: 'doc_in', attachmentTitle: 'incoming_no', formWidth: '860px',
    columns: [
      { key: 'incoming_no', label: 'លេខឯកសារចូល', width: 130 },
      { key: 'subject', label: 'ខ្លឹមសារឯកសារ', minWidth: 260 },
      { key: 'doc_date', label: 'ថ្ងៃខែឆ្នាំ', type: 'date', width: 110 },
      { key: 'document_type_name', label: 'ប្រភេទឯកសារ', width: 130 },
      { key: 'from_unit_name', label: 'មកពីស្ថាប័នកងឯកភាព', minWidth: 160 },
    ],
    filters: [{ key: 'document_type_id', label: 'ប្រភេទ', type: 'select', options: 'document_types' },
      { key: 'from_unit_id', label: 'ស្ថាប័នកងឯកភាព', type: 'unit' }, ...dateRange],
    fields: [
      { key: 'incoming_no', label: 'លេខឯកសារចូល', required: true, span: 8 },
      { key: 'doc_date', label: 'ថ្ងៃខែឆ្នាំឯកសារ', type: 'date', required: true, span: 8 },
      { key: 'received_date', label: 'ថ្ងៃទទួល', type: 'date', span: 8 },
      { key: 'subject', label: 'ខ្លឹមសារឯកសារ', type: 'textarea', required: true },
      { key: 'document_type_id', label: 'ប្រភេទឯកសារ', type: 'select', options: 'document_types', span: 12 },
      { key: 'from_unit_id', label: 'មកពីស្ថាប័នកងឯកភាព', type: 'unit', span: 12 },
      { key: 'from_unit', label: 'ឬ មកពីស្ថាប័នក្រៅ (សរសេរជាអក្សរ)', span: 24 },
      { key: 'remarks', label: 'កំណត់សម្គាល់', type: 'textarea', rows: 2 },
    ],
  },
  docOut: {
    title: 'ឯកសារចេញ', endpoint: '/documents/outgoing', module: 'doc_out', attachments: 'doc_out', attachmentTitle: 'outgoing_no', formWidth: '860px',
    columns: [
      { key: 'outgoing_no', label: 'លេខ', width: 110 },
      { key: 'subject', label: 'ខ្លឹមសារឯកសារ', minWidth: 240 },
      { key: 'doc_date', label: 'ថ្ងៃខែឆ្នាំ', type: 'date', width: 110 },
      { key: 'document_type_name', label: 'ប្រភេទឯកសារ', width: 120 },
      { key: 'unit_name', label: 'អង្គភាព', minWidth: 140 },
      { key: 'recipient_name', label: 'អ្នកទទួល', width: 130 },
      { key: 'recipient_phone', label: 'លេខទូរសព្ទអ្នកទទួល', width: 140 },
    ],
    filters: [{ key: 'document_type_id', label: 'ប្រភេទ', type: 'select', options: 'document_types' },
      { key: 'unit_id', label: 'អង្គភាព', type: 'unit' }, ...dateRange],
    fields: [
      { key: 'outgoing_no', label: 'លេខ (ទុកទំនេរ = បង្កើតស្វ័យប្រវត្តិ)', span: 12 },
      { key: 'doc_date', label: 'ថ្ងៃខែឆ្នាំ', type: 'date', required: true, span: 12 },
      { key: 'subject', label: 'ខ្លឹមសារឯកសារ', type: 'textarea', required: true },
      { key: 'document_type_id', label: 'ប្រភេទឯកសារ', type: 'select', options: 'document_types', span: 12 },
      { key: 'unit_id', label: 'អង្គភាព', type: 'unit', span: 12 },
      { key: 'recipient_name', label: 'អ្នកទទួល', span: 12 },
      { key: 'recipient_phone', label: 'លេខទូរសព្ទអ្នកទទួល', span: 12 },
      { key: 'remarks', label: 'កំណត់សម្គាល់', type: 'textarea', rows: 2 },
    ],
  },
  discipline: {
    title: 'ការងារវិន័យ និងទណ្ឌកម្ម', endpoint: '/discipline', module: 'discipline', attachments: 'discipline', formWidth: '720px',
    columns: [...soldierCols,
      { key: 'discipline_type_name', label: 'ប្រភេទទណ្ឌកម្ម', width: 150 },
      { key: 'decision_no', label: 'លេខលិខិត', width: 110 },
      { key: 'decision_date', label: 'ថ្ងៃខែឆ្នាំ', type: 'date', width: 110 },
      { key: 'end_date', label: 'ផុតកំណត់', type: 'date', width: 110 }],
    filters: [{ key: 'discipline_type_id', label: 'ប្រភេទ', type: 'select', options: 'lookup:discipline_type' }, ...dateRange],
    fields: [soldierField,
      { key: 'discipline_type_id', label: 'ប្រភេទទណ្ឌកម្ម', type: 'select', options: 'lookup:discipline_type', span: 12 },
      { key: 'decision_no', label: 'លេខលិខិត/សេចក្ដីសម្រេច', span: 12 },
      { key: 'decision_date', label: 'ថ្ងៃខែឆ្នាំលិខិត', type: 'date', span: 8 },
      { key: 'start_date', label: 'ចាប់ពីថ្ងៃ', type: 'date', span: 8 },
      { key: 'end_date', label: 'ដល់ថ្ងៃ', type: 'date', span: 8 },
      { key: 'reason', label: 'មូលហេតុ', type: 'textarea' }],
  },
  awards: {
    title: 'ការងារសរសើរ និងគ្រឿងឥស្សរិយយស', endpoint: '/awards', module: 'awards', attachments: 'award', formWidth: '720px',
    columns: [...soldierCols,
      { key: 'award_type_name', label: 'ប្រភេទ', width: 160 },
      { key: 'decision_no', label: 'លេខលិខិត', width: 110 },
      { key: 'decision_date', label: 'ថ្ងៃខែឆ្នាំ', type: 'date', width: 110 }],
    filters: [{ key: 'award_type_id', label: 'ប្រភេទ', type: 'select', options: 'lookup:award_type' }, ...dateRange],
    fields: [soldierField,
      { key: 'award_type_id', label: 'ប្រភេទ (ប័ណ្ណសរសើរ/លិខិតសរសើរ/មេដាយ)', type: 'select', options: 'lookup:award_type', span: 12 },
      { key: 'decision_no', label: 'លេខលិខិត', span: 6 },
      { key: 'decision_date', label: 'ថ្ងៃខែឆ្នាំ', type: 'date', span: 6 },
      { key: 'reason', label: 'ខ្លឹមសារ/មូលហេតុ', type: 'textarea' }],
  },
  retirement: {
    title: 'សោធននិវត្តន៍ និងយោធិនប្រភេទ២', endpoint: '/retirements', module: 'retirement', attachments: 'retirement', formWidth: '720px',
    columns: [...soldierCols,
      { key: 'type_name', label: 'ប្រភេទ', width: 140 },
      { key: 'decision_no', label: 'លេខលិខិត', width: 110 },
      { key: 'effective_date', label: 'ចូលជាធរមាន', type: 'date', width: 120 },
      { key: 'pension_amount', label: 'ប្រាក់សោធន', width: 110 }],
    filters: [{ key: 'type', label: 'ប្រភេទ', type: 'select', options: RETIREMENT_TYPES }, ...dateRange],
    fields: [soldierField,
      { key: 'type', label: 'ប្រភេទ', type: 'select', required: true, default: 'pension', span: 12,
        options: RETIREMENT_TYPES },
      { key: 'effective_date', label: 'ថ្ងៃចូលជាធរមាន', type: 'date', required: true, span: 12 },
      { key: 'decision_no', label: 'លេខលិខិត', span: 8 },
      { key: 'decision_date', label: 'ថ្ងៃខែឆ្នាំលិខិត', type: 'date', span: 8 },
      { key: 'pension_amount', label: 'ប្រាក់សោធន (រៀល)', type: 'number', span: 8 },
      { key: 'notes', label: 'កំណត់សម្គាល់', type: 'textarea' }],
  },
  separation: {
    title: 'យោធិនចេញពីជួរ', endpoint: '/separations', module: 'separation', attachments: 'separation', formWidth: '720px',
    columns: [...soldierCols,
      { key: 'reason_name', label: 'មូលហេតុ', width: 150 },
      { key: 'decision_no', label: 'លេខលិខិត', width: 110 },
      { key: 'effective_date', label: 'ចូលជាធរមាន', type: 'date', width: 120 }],
    filters: [{ key: 'reason_id', label: 'មូលហេតុ', type: 'select', options: 'lookup:separation_reason' }, ...dateRange],
    fields: [soldierField,
      { key: 'reason_id', label: 'មូលហេតុ', type: 'select', options: 'lookup:separation_reason', span: 12 },
      { key: 'effective_date', label: 'ថ្ងៃចូលជាធរមាន', type: 'date', required: true, span: 12 },
      { key: 'decision_no', label: 'លេខលិខិត', span: 12 },
      { key: 'decision_date', label: 'ថ្ងៃខែឆ្នាំលិខិត', type: 'date', span: 12 },
      { key: 'notes', label: 'កំណត់សម្គាល់', type: 'textarea' }],
  },
  strength: {
    title: 'ការងារកើនថយ', endpoint: '/strength-movements', module: 'strength', formWidth: '640px',
    canEdit: (r) => !r.source_table, canDelete: (r) => !r.source_table,
    columns: [
      { key: 'movement_date', label: 'កាលបរិច្ឆេទ', type: 'date', width: 110 },
      { key: 'direction', label: 'កើន/ថយ', width: 90, value: (r) => (r.direction === 'in' ? 'កើន' : 'ថយ'), tag: (r) => (r.direction === 'in' ? 'success' : 'danger') },
      { key: 'reason_name', label: 'មូលហេតុ', width: 170 },
      ...soldierCols.slice(0, 3),
      { key: 'unit_name', label: 'អង្គភាព', minWidth: 150 },
      { key: 'note', label: 'កំណត់សម្គាល់', minWidth: 140 },
    ],
    filters: [
      { key: 'direction', label: 'កើន/ថយ', type: 'select', width: '110px', options: [{ value: 'in', label: 'កើន' }, { value: 'out', label: 'ថយ' }] },
      { key: 'unit_id', label: 'អង្គភាព', type: 'unit' }, ...dateRange],
    fields: [soldierField,
      { key: 'direction', label: 'កើន/ថយ', type: 'select', required: true, span: 12, options: [{ value: 'in', label: 'កើន' }, { value: 'out', label: 'ថយ' }] },
      { key: 'reason', label: 'មូលហេតុ', type: 'select', required: true, span: 12, options: [
        { value: 'recruit', label: 'ចូលបម្រើថ្មី' }, { value: 'reinstate', label: 'ចូលបម្រើវិញ' },
        { value: 'transfer_in', label: 'ផ្លាស់មកពីអង្គភាពផ្សេង' }, { value: 'transfer_out', label: 'ផ្លាស់ទៅអង្គភាពផ្សេង' },
        { value: 'other', label: 'ផ្សេងៗ' }] },
      { key: 'unit_id', label: 'អង្គភាព', type: 'unit', span: 12 },
      { key: 'movement_date', label: 'កាលបរិច្ឆេទ', type: 'date', required: true, span: 12 },
      { key: 'note', label: 'កំណត់សម្គាល់', type: 'textarea', rows: 2 }],
  },
  countries: {
    title: 'ប្រទេស', endpoint: '/countries', module: 'lookups', refreshLookups: true,
    columns: [...nameCols, activeCol],
    fields: [...nameFields, activeField],
  },
}

export function lookupConfig(category, label) {
  return {
    title: label, endpoint: '/lookups', module: 'lookups', refreshLookups: true, fixedParams: { category },
    columns: [...nameCols, { key: 'code', label: 'កូដ', width: 120 }, { key: 'sort_order', label: 'លំដាប់', width: 90 }, activeCol],
    fields: [...nameFields, { key: 'code', label: 'កូដ (ប្រើក្នុងប្រព័ន្ធ)', span: 8 },
      { key: 'sort_order', label: 'លំដាប់', type: 'number', default: 0, span: 8 }, { ...activeField, span: 8 }],
  }
}

export function geoConfig(level, parentKey, parentId) {
  const meta = {
    provinces: { title: 'រាជធានី/ខេត្ត', types: ['រាជធានី', 'ខេត្ត'] },
    districts: { title: 'ស្រុក/ក្រុង/ខណ្ឌ', types: ['ស្រុក', 'ក្រុង', 'ខណ្ឌ'] },
    communes: { title: 'ឃុំ/សង្កាត់', types: ['ឃុំ', 'សង្កាត់'] },
    villages: { title: 'ភូមិ', types: null },
  }[level]
  const fields = [{ key: 'id', label: 'លេខកូដ', type: 'number', required: true, span: 12, disabled: (row) => !!row.id }]
  if (meta.types) fields.push({ key: 'type', label: 'ប្រភេទ', type: 'select', required: true, default: meta.types[0], span: 12, options: meta.types.map((t) => ({ value: t, label: t })) })
  fields.push(...nameFields, activeField)
  return {
    title: meta.title, endpoint: `/geo/${level}`, module: 'geography',
    fixedParams: parentKey ? { [parentKey]: parentId } : {},
    columns: [{ key: 'id', label: 'លេខកូដ', width: 110 }, ...(meta.types ? [{ key: 'type', label: 'ប្រភេទ', width: 100 }] : []), ...nameCols, activeCol],
    fields,
    actionWidth: 190,
  }
}
