import * as React from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { AppSidebar, crmNav, workspaceNav } from './AppSidebar'
import type { Notice } from './CrmTopBar'

export type AppContext = {
  rootLabel: string
  rootPath: string
  scopes: string[]
  scope: string
  setScope: (s: string) => void
  notices: Notice[]
  user: { initials: string; name: string; role: string }
  openMenu: () => void
}

/**
 * Shell for signed-in apps. `.app-shell` switches the ground to #F7F7F5 and
 * cards to bordered style. Sidebar is 240px on desktop and a slide-in drawer on phones.
 * Data (user, scopes, notices) comes from FastAPI: GET /api/me, /api/notifications.
 */
export function AppLayout({ kind }: { kind: 'crm' | 'workspace' }) {
  const [scope, setScope] = React.useState('National HQ')
  const [menu, setMenu] = React.useState(false)
  const { pathname } = useLocation()
  React.useEffect(() => setMenu(false), [pathname])
  const ctx: AppContext = {
    rootLabel: kind === 'crm' ? 'Party CRM' : 'Workspace',
    rootPath: kind === 'crm' ? '/crm' : '/ws',
    scopes: ['National HQ', '[County] branch'],
    scope, setScope,
    notices: [
      { title: '[00] membership applications to verify', when: '[0] min ago', to: '/crm/members' },
      { title: 'Timetable change waiting for your sign-off', when: '[0] hours ago', to: '/crm/nominations/timetable' },
      { title: 'New appeal filed: [Seat]', when: 'Yesterday', to: '/crm/appeals' },
    ],
    user: { initials: '[AB]', name: '[Staff name]', role: kind === 'crm' ? 'HQ admin' : 'Campaign manager' },
    openMenu: () => setMenu(true),
  }
  return (
    <div className="app-shell flex min-h-dvh flex-col md:flex-row">
      {menu ? <button aria-label="Close menu" onClick={() => setMenu(false)} className="fixed inset-0 z-40 bg-ink/40 md:hidden" /> : null}
      {kind === 'crm' ? (
        <AppSidebar items={crmNav} tone="dark" subtitle="Secretariat · HQ" open={menu} />
      ) : (
        <AppSidebar items={workspaceNav} tone="light" eyebrow="Pamoja Party · Field plan" title="[Candidate] for MP" subtitle="[Constituency], [County]" open={menu} />
      )}
      <Outlet context={ctx} />
    </div>
  )
}
