/** Sidebar menu (plan.txt §3). `perm` hides items the user cannot view. */
export const menu = [
  { key: 'dashboard', icon: 'Odometer', to: '/', perm: 'dashboard.view' },
  {
    key: 'org', icon: 'OfficeBuilding', children: [
      { key: 'units', to: '/org/units', perm: 'org_units.view' },
      { key: 'ranks', to: '/org/ranks', perm: 'ranks.view' },
      { key: 'positions', to: '/org/positions', perm: 'positions.view' },
      { key: 'staffing', to: '/org/staffing', perm: 'positions.view' },
      { key: 'specialties', to: '/org/specialties', perm: 'specialties.view' },
      { key: 'docTypes', to: '/org/document-types', perm: 'doc_types.view' },
    ],
  },
  {
    key: 'documents', icon: 'Document', children: [
      { key: 'docIn', to: '/documents/incoming', perm: 'doc_in.view' },
      { key: 'docOut', to: '/documents/outgoing', perm: 'doc_out.view' },
    ],
  },
  {
    key: 'soldiers', icon: 'User', children: [
      { key: 'soldierList', to: '/soldiers', perm: 'soldiers.view' },
      { key: 'soldierNew', to: '/soldiers/new', perm: 'soldiers.create' },
      { key: 'strength', to: '/strength', perm: 'strength.view' },
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
  { key: 'discipline', icon: 'Warning', to: '/discipline', perm: 'discipline.view' },
  { key: 'awards', icon: 'Trophy', to: '/awards', perm: 'awards.view' },
  { key: 'retirement', icon: 'Calendar', to: '/retirement', perm: 'retirement.view' },
  { key: 'separation', icon: 'Remove', to: '/separation', perm: 'separation.view' },
  {
    key: 'recruitment', icon: 'Flag', children: [
      { key: 'conscripts', to: '/conscripts', perm: 'conscripts.view' },
    ],
  },
  { key: 'reports', icon: 'DataAnalysis', to: '/reports', perm: 'reports.view' },
  {
    key: 'settings', icon: 'Setting', children: [
      { key: 'users', to: '/settings/users', perm: 'users.view' },
      { key: 'roles', to: '/settings/roles', perm: 'roles.view' },
      { key: 'geography', to: '/settings/geography', perm: 'geography.view' },
      { key: 'lookups', to: '/settings/lookups', perm: 'lookups.view' },
      { key: 'countries', to: '/settings/countries', perm: 'lookups.view' },
      { key: 'system', to: '/settings/system', perm: 'settings.view' },
      { key: 'audit', to: '/settings/audit', perm: 'audit.view' },
    ],
  },
  { key: 'about', icon: 'InfoFilled', to: '/about' },
]
