/** Sidebar menu, ordered as in New.txt. `perm` hides items the user cannot view. */
export const menu = [
  { key: 'dashboard', icon: 'Odometer', to: '/', perm: 'dashboard.view' },
  {
    key: 'org', icon: 'OfficeBuilding', children: [
      { key: 'units', to: '/org/units', perm: 'org_units.view' },
      { key: 'ranks', to: '/org/ranks', perm: 'ranks.view' },
      { key: 'positions', to: '/org/positions', perm: 'positions.view' },
      { key: 'staffing', to: '/org/staffing', perm: 'positions.view' },
      { key: 'specialties', to: '/org/specialties', perm: 'specialties.view' },
      { key: 'sections', to: '/settings/lookups?category=specialty_section', perm: 'lookups.view' },
      { key: 'educationLevels', to: '/settings/lookups?category=education_level', perm: 'lookups.view' },
      { key: 'geography', to: '/settings/geography', perm: 'geography.view' },
      { key: 'legalDocs', to: '/documents/legal', perm: ['doc_in.view', 'doc_out.view'] },
      { key: 'docTypes', to: '/org/document-types', perm: 'doc_types.view' },
    ],
  },
  {
    key: 'archives', icon: 'Document', children: [
      { key: 'docOut', to: '/documents/outgoing', perm: 'doc_out.view' },
      { key: 'docIn', to: '/documents/incoming', perm: 'doc_in.view' },
    ],
  },
  {
    key: 'recruitment', icon: 'Flag', children: [
      { key: 'soldierIntake', to: '/soldiers/import', perm: 'soldiers.create' },
      { key: 'conscripts', to: '/conscripts', perm: 'conscripts.view' },
    ],
  },
  {
    key: 'soldiers', icon: 'User', children: [
      { key: 'soldierList', to: '/soldiers', perm: 'soldiers.view' },
      { key: 'unitTransfers', to: '/strength', perm: 'strength.view' },
      { key: 'compare', to: '/soldiers/compare', perm: 'soldiers.view' },
    ],
  },
  {
    key: 'decisions', icon: 'Medal', children: [
      { key: 'appoint', to: '/decisions/appoint', perm: 'decisions_appoint.view' },
      { key: 'transfer', to: '/decisions/transfer', perm: 'decisions_transfer.view' },
      { key: 'promote', to: '/decisions/promote', perm: 'decisions_promote.view' },
    ],
  },
  {
    key: 'training', icon: 'Reading', children: [
      { key: 'education', to: '/training/education', perm: 'soldiers.view' },
      { key: 'specialtyTraining', to: '/training/specialty', perm: 'soldiers.view' },
      { key: 'longCourses', to: '/training/long', perm: 'training.view' },
      { key: 'shortCourses', to: '/training/short', perm: 'training.view' },
    ],
  },
  { key: 'awards', icon: 'Trophy', to: '/awards', perm: 'awards.view' },
  { key: 'discipline', icon: 'Warning', to: '/discipline', perm: 'discipline.view' },
  { key: 'retirement', icon: 'Calendar', to: '/retirement', perm: 'retirement.view' },
  { key: 'separation', icon: 'Remove', to: '/separation', perm: 'separation.view' },
  { key: 'reports', icon: 'DataAnalysis', to: '/reports', perm: 'reports.view' },
  {
    key: 'settings', icon: 'Setting', children: [
      { key: 'users', to: '/settings/users', perm: 'users.view' },
      { key: 'roles', to: '/settings/roles', perm: 'roles.view' },
      { key: 'lookups', to: '/settings/lookups', perm: 'lookups.view' },
      { key: 'countries', to: '/settings/countries', perm: 'lookups.view' },
      { key: 'system', to: '/settings/system', perm: 'settings.view' },
      { key: 'audit', to: '/settings/audit', perm: 'audit.view' },
    ],
  },
  { key: 'about', icon: 'InfoFilled', to: '/about' },
]
