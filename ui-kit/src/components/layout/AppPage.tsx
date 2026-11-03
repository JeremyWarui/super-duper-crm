import * as React from 'react'
import { useOutletContext } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { CrmTopBar } from './CrmTopBar'
import type { AppContext } from './AppLayout'

/**
 * One CRM / workspace screen. Pins the top bar and this page's header together
 * (sticky), then renders the content with 28px/32px padding.
 *
 *   <AppPage crumb="Members" context="Verification queue" title="Membership verification"
 *            actions={<Button shape="rounded">Export</Button>}>
 *     …cards…
 *   </AppPage>
 */
export function AppPage({ crumb, context, title, actions, children, gap = 24, className }: {
  crumb: string | { label: string; to?: string }[]
  context?: React.ReactNode   // small line above the title (window dates, credit, back link)
  title: React.ReactNode
  actions?: React.ReactNode   // buttons / filters / status pill on the right of the title
  children: React.ReactNode
  gap?: 20 | 22 | 24
  className?: string
}) {
  const app = useOutletContext<AppContext>()
  const crumbs = [{ label: app.rootLabel, to: app.rootPath }, ...(typeof crumb === 'string' ? [{ label: crumb }] : crumb)]
  return (
    <div className="flex min-w-0 flex-1 flex-col">
      <div className="sticky top-0 z-20">
        <CrmTopBar crumbs={crumbs} scopes={app.scopes} scope={app.scope} onScope={app.setScope} notices={app.notices} user={app.user} onMenu={app.openMenu} />
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-black/[0.06] bg-ground/90 px-app py-[18px] backdrop-blur-md">
          <div className="flex flex-col gap-1">
            {context ? <div className="text-ui font-semibold text-muted-foreground">{context}</div> : null}
            <h1 className="font-display text-h2-app font-extrabold tracking-[-0.02em]">{title}</h1>
          </div>
          {actions ? <div className="flex flex-wrap items-center gap-2.5">{actions}</div> : null}
        </header>
      </div>
      <div className={cn('flex flex-col px-app pt-7 pb-10', gap === 20 ? 'gap-5' : gap === 22 ? 'gap-[22px]' : 'gap-6', className)}>{children}</div>
    </div>
  )
}
