import * as React from 'react'
import { Link } from 'react-router-dom'
import { Menu } from 'lucide-react'
import { UserMenu } from './CrmTopBar'

/**
 * A campaign workspace's top bar, 64px: breadcrumb, a wide search in the middle, then the
 * workspace's tools (area picker, notifications, help) and the signed-in person.
 */
export function WsTopBar({ crumbs, user, onSignOut, onMenu, search, tools }: {
  crumbs: { label: string; to?: string }[]
  user: { initials: string; name: string; role: string }
  onSignOut: () => void
  onMenu?: () => void
  search?: React.ReactNode
  tools?: React.ReactNode
}) {
  return (
    <div className="border-b border-black/[0.06] bg-white">
      <div className="box-border flex min-h-16 flex-wrap items-center gap-x-5 gap-y-2.5 px-4 py-2.5 md:px-app">
        <button type="button" onClick={onMenu} aria-label="Open menu" className="flex size-11 cursor-pointer items-center justify-center rounded-full hover:bg-stone md:hidden">
          <Menu className="size-5" />
        </button>
        <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-ui font-semibold text-muted-foreground">
          {crumbs.map((c, i) => (
            <React.Fragment key={i}>
              {i > 0 ? <span aria-hidden>/</span> : null}
              {c.to ? <Link to={c.to} className="inline-flex min-h-11 items-center text-muted-foreground no-underline hover:text-ink md:min-h-0">{c.label}</Link> : <span className="text-ink">{c.label}</span>}
            </React.Fragment>
          ))}
        </nav>
        {search ? <div className="order-last min-w-0 basis-full md:order-none md:max-w-[520px] md:flex-[1_1_280px] md:basis-auto">{search}</div> : null}
        <div className="ml-auto flex items-center gap-1.5">
          {tools}
          <UserMenu user={user} onSignOut={onSignOut} />
        </div>
      </div>
    </div>
  )
}
