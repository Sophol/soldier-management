import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '@/stores/auth'
import { useLookups } from '@/stores/lookups'
import MainLayout from '@/layouts/MainLayout.vue'

// import.meta.glob lets Vite see every view, including those in sub-folders
const views = import.meta.glob('../views/**/*.vue')
const v = (p) => {
  const loader = views[`../views/${p}.vue`]
  if (!loader) throw new Error(`View not found: ${p}`)
  return loader
}

const routes = [
  { path: '/login', name: 'login', component: v('Login'), meta: { public: true } },
  { path: '/soldiers/:id/print', component: v('soldiers/SoldierPrint'), meta: { perm: 'soldiers.print' } },
  { path: '/decisions/:id/print', component: v('decisions/DecisionPrint') },
  { path: '/reports/print', component: v('reports/ReportPrint'), meta: { perm: 'reports.print' } },
  {
    path: '/',
    component: MainLayout,
    children: [
      { path: '', name: 'dashboard', component: v('Dashboard'), meta: { perm: 'dashboard.view' } },
      { path: 'org/units', component: v('org/Units'), meta: { perm: 'org_units.view' } },
      { path: 'org/ranks', component: v('org/Ranks'), meta: { perm: 'ranks.view' } },
      { path: 'org/positions', component: v('CrudView'), props: { name: 'positions' }, meta: { perm: 'positions.view' } },
      { path: 'org/staffing', component: v('org/Staffing'), meta: { perm: 'positions.view' } },
      { path: 'org/specialties', component: v('CrudView'), props: { name: 'specialties' }, meta: { perm: 'specialties.view' } },
      { path: 'org/document-types', component: v('CrudView'), props: { name: 'documentTypes' }, meta: { perm: 'doc_types.view' } },
      { path: 'documents/incoming', component: v('CrudView'), props: { name: 'docIn' }, meta: { perm: 'doc_in.view' } },
      { path: 'documents/outgoing', component: v('CrudView'), props: { name: 'docOut' }, meta: { perm: 'doc_out.view' } },
      { path: 'soldiers', component: v('soldiers/SoldierList'), meta: { perm: 'soldiers.view' } },
      { path: 'soldiers/new', component: v('soldiers/SoldierForm'), meta: { perm: 'soldiers.create' } },
      { path: 'soldiers/:id', component: v('soldiers/SoldierView'), meta: { perm: 'soldiers.view' } },
      { path: 'soldiers/:id/edit', component: v('soldiers/SoldierForm'), meta: { perm: 'soldiers.update' } },
      { path: 'strength', component: v('CrudView'), props: { name: 'strength' }, meta: { perm: 'strength.view' } },
      { path: 'decisions/:kind(appoint|transfer|promote)', component: v('decisions/DecisionList') },
      { path: 'training/education', component: v('training/TrainingStats'), props: { by: 'education' }, meta: { perm: 'soldiers.view' } },
      { path: 'training/specialty', component: v('training/TrainingStats'), props: { by: 'specialty' }, meta: { perm: 'soldiers.view' } },
      { path: 'training/:type(long|short)', component: v('training/Courses'), meta: { perm: 'training.view' } },
      { path: 'discipline', component: v('CrudView'), props: { name: 'discipline' }, meta: { perm: 'discipline.view' } },
      { path: 'awards', component: v('CrudView'), props: { name: 'awards' }, meta: { perm: 'awards.view' } },
      { path: 'retirement', component: v('CrudView'), props: { name: 'retirement' }, meta: { perm: 'retirement.view' } },
      { path: 'separation', component: v('CrudView'), props: { name: 'separation' }, meta: { perm: 'separation.view' } },
      { path: 'conscripts', component: v('conscripts/ConscriptList'), meta: { perm: 'conscripts.view' } },
      { path: 'conscripts/:id(\\d+)', component: v('conscripts/ConscriptView'), meta: { perm: 'conscripts.view' } },
      { path: 'reports', component: v('reports/Reports'), meta: { perm: 'reports.view' } },
      { path: 'settings/users', component: v('settings/Users'), meta: { perm: 'users.view' } },
      { path: 'settings/roles', component: v('settings/Roles'), meta: { perm: 'roles.view' } },
      { path: 'settings/geography', component: v('settings/Geography'), meta: { perm: 'geography.view' } },
      { path: 'settings/lookups', component: v('settings/Lookups'), meta: { perm: 'lookups.view' } },
      { path: 'settings/countries', component: v('CrudView'), props: { name: 'countries' }, meta: { perm: 'lookups.view' } },
      { path: 'settings/system', component: v('settings/SystemSettings'), meta: { perm: 'settings.view' } },
      { path: 'settings/audit', component: v('settings/AuditLog'), meta: { perm: 'audit.view' } },
      { path: 'account', component: v('Account') },
      { path: 'about', component: v('About') },
      { path: 'forbidden', component: v('Forbidden') },
      { path: ':pathMatch(.*)*', component: v('NotFound') },
    ],
  },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  const auth = useAuth()
  if (!auth.loaded) await auth.fetchMe()
  if (to.meta.public) return auth.isLoggedIn && to.name === 'login' ? '/' : true
  if (!auth.isLoggedIn) return { path: '/login', query: { next: to.fullPath } }
  await useLookups().load()
  if (to.path.startsWith('/decisions/') && to.params.kind && !auth.can(`decisions_${to.params.kind}.view`)) return '/forbidden'
  if (to.meta.perm && !auth.can(to.meta.perm)) {
    // the dashboard is the default landing page; fall back to the first page the user can open
    return to.name === 'dashboard' ? '/soldiers' : '/forbidden'
  }
  return true
})

router.onError((err) => {
  console.error('Navigation error:', err)
})

export default router
