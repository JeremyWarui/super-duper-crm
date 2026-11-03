import * as React from 'react'
import { Link } from 'react-router-dom'
import { Bell, Menu, Search } from 'lucide-react'
import { NativeSelect } from '@/components/ui/input'
import { Popover, PopoverContent, PopoverTrigger, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/popover'

export type Notice = { title: string; when: string; to: string }

/**
 * Top bar shared by every CRM / workspace screen (mockup: CrmTopBar), 64px.
 * Breadcrumb · search (Ctrl K) · scope · notifications · help · user.
 * Scope options come from the user's roles: a county official gets only their county.
 */
export function CrmTopBar({ crumbs, scopes, scope, onScope, notices, user, onMenu }: {
  crumbs: { label: string; to?: string }[]
  scopes: string[]
  scope: string
  onScope: (s: string) => void
  notices: Notice[]
  user: { initials: string; name: string; role: string }
  onMenu?: () => void
}) {
  const searchRef = React.useRef<HTMLInputElement>(null)
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); searchRef.current?.focus() } }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  return (
    <div className="border-b border-black/[0.06] bg-white">
      <div className="box-border flex min-h-16 flex-wrap items-center gap-x-5 gap-y-2.5 px-app py-2.5">
        <button type="button" onClick={onMenu} aria-label="Open menu" className="flex size-[42px] cursor-pointer items-center justify-center rounded-full hover:bg-stone md:hidden"><Menu className="size-5" /></button>
        <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-ui font-semibold text-muted-foreground">
          {crumbs.map((c, i) => (
            <React.Fragment key={i}>
              {i > 0 ? <span aria-hidden>/</span> : null}
              {c.to ? <Link to={c.to} className="text-muted-foreground no-underline hover:text-ink">{c.label}</Link> : <span className="text-ink">{c.label}</span>}
            </React.Fragment>
          ))}
        </nav>
        <div className="flex h-[42px] max-w-[520px] flex-[1_1_280px] items-center gap-2.5 rounded-full bg-stone px-4">
          <Search aria-hidden className="size-4 text-muted-foreground" strokeWidth={2.2} />
          <input ref={searchRef} type="search" aria-label="Search the CRM" placeholder="Search members, branches, aspirants…" className="min-w-0 flex-1 border-0 bg-transparent text-body outline-none" />
          <kbd className="rounded-sm border border-line-2 bg-white px-1.5 py-0.5 text-meta font-bold text-muted-foreground">Ctrl K</kbd>
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          <label className="flex items-center gap-1.5 text-small font-semibold text-muted-foreground">
            Scope
            <NativeSelect value={scope} onChange={(e) => onScope(e.target.value)} className="h-10 rounded-full border border-line-control text-ui font-bold">
              {scopes.map((s) => <option key={s}>{s}</option>)}
            </NativeSelect>
          </label>
          <Popover>
            <PopoverTrigger aria-label={`Notifications, ${notices.length} new`} className="relative flex size-[42px] cursor-pointer items-center justify-center rounded-full hover:bg-stone">
              <Bell aria-hidden className="size-5" />
              {notices.length ? <span aria-hidden className="absolute top-1.5 right-1.5 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-destructive px-1 text-[11px] font-extrabold text-white">{notices.length}</span> : null}
            </PopoverTrigger>
            <PopoverContent>
              {notices.map((n) => (
                <Link key={n.title} to={n.to} className="flex flex-col gap-0.5 rounded-lg px-3 py-2.5 text-ink no-underline hover:bg-stone hover:text-ink">
                  <span className="text-ui font-bold">{n.title}</span>
                  <span className="text-meta text-muted-foreground">{n.when}</span>
                </Link>
              ))}
            </PopoverContent>
          </Popover>
          <Link to="/help" aria-label="Help" className="flex size-[42px] items-center justify-center rounded-full font-extrabold text-ink no-underline hover:bg-stone hover:text-ink">?</Link>
          <DropdownMenu>
            <DropdownMenuTrigger className="flex cursor-pointer items-center gap-2.5 rounded-full bg-stone py-1 pr-3 pl-1">
              <span className="flex size-[34px] items-center justify-center rounded-full bg-primary text-small font-extrabold text-accent">{user.initials}</span>
              <span className="hidden flex-col text-left leading-[1.15] sm:flex"><span className="text-ui font-bold">{user.name}</span><span className="text-meta text-muted-foreground">{user.role}</span></span>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuLabel>Signed in as {user.role}</DropdownMenuLabel>
              <DropdownMenuItem asChild><Link to="/where-to">Switch workspace</Link></DropdownMenuItem>
              <DropdownMenuItem asChild><Link to="/account/security">2-step sign-in &amp; security</Link></DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild><Link to="/sign-out">Sign out</Link></DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </div>
  )
}
