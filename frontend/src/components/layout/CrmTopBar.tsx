import * as React from 'react'
import { Link } from 'react-router-dom'
import { Menu } from 'lucide-react'
import { usePanel } from '@/lib/usePanel'

/** The signed-in person's chip; it opens a small panel with Sign out. Escape or a click outside closes it. */
export function UserMenu({ user, onSignOut }: { user: { initials: string; name: string; role: string }; onSignOut: () => void }) {
  const { open, setOpen, ref } = usePanel()
  return (
    <div ref={ref} className="relative">
      <button type="button" aria-expanded={open} aria-controls="user-menu" onClick={() => setOpen(!open)} className="flex min-h-11 cursor-pointer items-center gap-2.5 rounded-full bg-stone py-1 pr-3 pl-1">
        <span className="flex size-[34px] items-center justify-center rounded-full bg-primary text-small font-extrabold text-accent">{user.initials}</span>
        <span className="hidden flex-col text-left leading-[1.15] sm:flex"><span className="text-ui font-bold">{user.name}</span><span className="text-meta text-muted-foreground">{user.role}</span></span>
      </button>
      {open ? (
        <div id="user-menu" className="absolute right-0 z-50 mt-2 flex w-60 flex-col gap-1 rounded-photo border border-line bg-white p-2 shadow-pop">
          <span className="px-3 py-2 text-meta font-bold text-muted-foreground">Signed in as {user.role}</span>
          <button type="button" onClick={onSignOut} className="min-h-11 cursor-pointer rounded-lg px-3 text-left text-ui font-bold hover:bg-stone">Sign out</button>
        </div>
      ) : null}
    </div>
  )
}

/** The 64px top bar of every CRM and workspace screen: breadcrumb, an optional wide search, any tools, the signed-in person. */
export function CrmTopBar({ crumbs, user, onSignOut, onMenu, search, tools }: {
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
