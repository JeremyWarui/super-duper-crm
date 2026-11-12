import * as React from 'react'
import { useLocation } from 'react-router-dom'
import { AppSidebar, type NavGroup, type NavItem } from './AppSidebar'
import { initials } from '@/lib/format'
import { ButtonShape } from '@/components/ui/button'

export type AppContext = {
  rootLabel: string
  rootPath: string
  user: { initials: string; name: string; role: string }
  onSignOut: () => void
  openMenu: () => void
  tools?: React.ReactNode
  slotHeaders?: boolean
  /** Replaces the default top bar, as a campaign workspace does. */
  topBar?: (bar: TopBarProps) => React.ReactNode
}

export type TopBarProps = {
  crumbs: { label: string; to?: string }[]
  user: { initials: string; name: string; role: string }
  onSignOut: () => void
  onMenu: () => void
}

const Ctx = React.createContext<AppContext | null>(null)
export const useAppShell = () => React.useContext(Ctx) as AppContext

/**
 * Shell for signed-in apps. `.app-shell` switches the ground to #F7F7F5 and cards to bordered style.
 * tone="dark" is the party CRM, tone="light" a campaign workspace. The sidebar is 240px on
 * desktop and a slide-in drawer on phones.
 */
export function AppLayout({ tone, nav = [], groups, brand, card, footer, topBar, rootLabel, rootPath, eyebrow, title, subtitle, user, onSignOut, tools, slotHeaders, children }: {
  tone: 'dark' | 'light'
  nav?: NavItem[]
  /** Grouped items with icons, for a campaign workspace. */
  groups?: NavGroup[]
  brand?: React.ReactNode
  card?: React.ReactNode
  footer?: React.ReactNode
  topBar?: (bar: TopBarProps) => React.ReactNode
  rootLabel: string
  rootPath: string
  eyebrow?: string
  title?: string
  subtitle?: string
  user: { name: string; role: string }
  onSignOut: () => void
  /** Search, notifications and help, shown in the top bar before the signed-in person. */
  tools?: React.ReactNode
  /** A page's own PageTitle becomes its frosted header. */
  slotHeaders?: boolean
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
    rootLabel, rootPath, onSignOut, tools, slotHeaders, topBar,
    user: { ...user, initials: initials(user.name) },
    openMenu: () => setMenu(true),
  }
  return (
    <Ctx.Provider value={ctx}>
      <ButtonShape.Provider value="rounded">
      <div className="app-shell flex min-h-dvh flex-col md:flex-row">
        {menu ? <button aria-label="Close menu" onClick={() => setMenu(false)} className="fixed inset-0 z-40 bg-ink/40 md:hidden" /> : null}
        <AppSidebar items={nav} groups={groups} tone={tone} label={rootLabel} eyebrow={eyebrow} title={title} subtitle={subtitle} home={rootPath} open={menu} brand={brand} card={card} footer={footer} />
        {children}
      </div>
      </ButtonShape.Provider>
    </Ctx.Provider>
  )
}
