import * as React from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/lib/utils'
import { CrmTopBar } from './CrmTopBar'
import { useAppShell } from './AppLayout'

/** The frosted page header: context line, title, and the page's actions on the right. */
export function PageHeader({ context, title, sub, actions }: {
  context?: React.ReactNode
  title: React.ReactNode
  sub?: React.ReactNode
  actions?: React.ReactNode
}) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-4 border-b border-black/[0.06] bg-ground/90 px-app py-[18px] backdrop-blur-md">
      <div className="flex flex-col gap-1">
        {context ? <div className="text-ui font-semibold text-muted-foreground">{context}</div> : null}
        <h1 className="font-display text-h2-app font-extrabold tracking-[-0.02em]">{title}</h1>
        {sub ? <div className="text-ui text-muted-foreground">{sub}</div> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2.5">{actions}</div> : null}
    </header>
  )
}

const HeaderSlot = React.createContext<{ node: HTMLElement | null } | null>(null)

/**
 * Inside a shell with `slotHeaders`, `slotted` is true and `rendered` puts the header into the
 * sticky frosted header (nothing until it mounts); elsewhere the caller renders in place.
 */
export function useSlottedHeader(header: React.ReactNode): { slotted: boolean; rendered: React.ReactNode } {
  const slot = React.useContext(HeaderSlot)
  if (!slot) return { slotted: false, rendered: null }
  return { slotted: true, rendered: slot.node ? createPortal(header, slot.node) : null }
}

/**
 * One CRM / workspace screen. Pins the top bar and this page's header together (sticky),
 * then renders the content with 28px/32px padding. Without a title there is no page header.
 *
 *   <AppPage crumb="Members" context="Verification queue" title="Membership verification"
 *            actions={<Button shape="rounded">Export</Button>}>
 *     …cards…
 *   </AppPage>
 */
export function AppPage({ crumb, context, title, actions, children, gap = 24, className }: {
  crumb: string | { label: string; to?: string }[]
  context?: React.ReactNode
  title?: React.ReactNode
  actions?: React.ReactNode
  children: React.ReactNode
  gap?: 20 | 22 | 24
  className?: string
}) {
  const app = useAppShell()
  const [slot, setSlot] = React.useState<HTMLDivElement | null>(null)
  const crumbs = [{ label: app.rootLabel, to: app.rootPath }, ...(typeof crumb === 'string' ? [{ label: crumb }] : crumb)]
  const slotted = app.slotHeaders && !title
  return (
    <div className="flex min-w-0 flex-1 flex-col">
      <div className="sticky top-0 z-20">
        {app.topBar
          ? app.topBar({ crumbs, user: app.user, onSignOut: app.onSignOut, onMenu: app.openMenu })
          : <CrmTopBar crumbs={crumbs} user={app.user} onSignOut={app.onSignOut} onMenu={app.openMenu} tools={app.tools} />}
        {title ? <PageHeader context={context} title={title} actions={actions} /> : null}
        {slotted ? <div ref={setSlot} /> : null}
      </div>
      <div className={cn('flex flex-col px-app pt-7 pb-10', gap === 20 ? 'gap-5' : gap === 22 ? 'gap-[22px]' : 'gap-6', className)}>
        <HeaderSlot.Provider value={slotted ? { node: slot } : null}>{children}</HeaderSlot.Provider>
      </div>
    </div>
  )
}
