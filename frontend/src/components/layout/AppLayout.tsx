import * as React from 'react'
import { useLocation } from 'react-router-dom'
import { AppSidebar, type NavItem } from './AppSidebar'

export type AppContext = {
  rootLabel: string
  rootPath: string
  user: { initials: string; name: string; role: string }
  onSignOut: () => void
  openMenu: () => void
}

const Ctx = React.createContext<AppContext | null>(null)
export const useAppShell = () => React.useContext(Ctx) as AppContext

const initialsOf = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase()

/**
 * Shell for signed-in apps. `.app-shell` switches the ground to #F7F7F5 and cards to bordered style.
 * tone="dark" is the party CRM, tone="light" a campaign workspace. The sidebar is 240px on
 * desktop and a slide-in drawer on phones.
 */
export function AppLayout({ tone, nav, rootLabel, rootPath, eyebrow, title, subtitle, user, onSignOut, children }: {
  tone: 'dark' | 'light'
  nav: NavItem[]
  rootLabel: string
  rootPath: string
  eyebrow?: string
  title?: string
  subtitle?: string
  user: { name: string; role: string }
  onSignOut: () => void
  children: React.ReactNode
}) {
  const [menu, setMenu] = React.useState(false)
  const { pathname } = useLocation()
  React.useEffect(() => setMenu(false), [pathname])
  React.useEffect(() => {
    if (!menu) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setMenu(false) }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [menu])
  const ctx: AppContext = {
    rootLabel, rootPath, onSignOut,
    user: { ...user, initials: initialsOf(user.name) },
    openMenu: () => setMenu(true),
  }
  return (
    <Ctx.Provider value={ctx}>
      <div className="app-shell flex min-h-dvh flex-col md:flex-row">
        {menu ? <button aria-label="Close menu" onClick={() => setMenu(false)} className="fixed inset-0 z-40 bg-ink/40 md:hidden" /> : null}
        <AppSidebar items={nav} tone={tone} eyebrow={eyebrow} title={title} subtitle={subtitle} home={rootPath} open={menu} />
        {children}
      </div>
    </Ctx.Provider>
  )
}
