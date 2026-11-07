import * as React from 'react'
import { Link } from 'react-router-dom'
import { Bell, CircleHelp, Search } from 'lucide-react'
import { useSite, usePartyNotifications, usePartySearch } from '@/api/hooks'
import { useInstall } from '@/app/site'
import { useCopy } from '@/copy'
import { plural } from '@/lib/format'
import { usePanel } from '@/lib/usePanel'

const PANEL = 'absolute right-0 z-50 mt-2 flex w-[min(92vw,380px)] flex-col gap-1 rounded-photo border border-line bg-white p-2 shadow-pop'
const ICON_BUTTON = 'relative flex size-11 cursor-pointer items-center justify-center rounded-full hover:bg-stone'
const ROW = 'flex min-h-11 flex-col justify-center rounded-lg px-3 py-1.5 text-ink no-underline hover:bg-stone'

const HIT_PATH: Record<string, string> = { member: '/party/members', aspirant: '/party/aspirants' }

type Hit = { kind: 'member' | 'aspirant'; id: string; label: string; detail: string }

/** Search the registers the caller's offices open; Ctrl K or Cmd K opens it. */
function PartySearch() {
  const { open, setOpen, ref } = usePanel()
  const [q, setQ] = React.useState('')
  const found = usePartySearch(q)
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setOpen(true) }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [setOpen])
  const hits = (found.data || []) as Hit[]
  return (
    <div ref={ref} className="relative">
      <button type="button" aria-expanded={open} aria-controls="party-search" onClick={() => setOpen(!open)}
        className="flex min-h-11 cursor-pointer items-center gap-2 rounded-full bg-stone px-3 text-ui font-semibold text-muted-foreground">
        <Search className="size-4" aria-hidden />
        <span className="hidden sm:inline">Search</span>
        <kbd className="hidden rounded border border-line bg-white px-1.5 text-meta lg:inline">Ctrl K</kbd>
      </button>
      {open ? (
        <div id="party-search" className={PANEL}>
          <input autoFocus aria-label="Search the party registers" placeholder="Name or phone" value={q} onChange={(e) => setQ(e.target.value)}
            className="min-h-11 rounded-lg border border-line px-3 text-ui outline-none focus:border-primary" />
          {q.trim().length < 2 ? <span className="px-3 py-2 text-meta text-muted-foreground">Type at least two letters.</span> : null}
          {found.error ? <span className="px-3 py-2 text-meta text-destructive">{(found.error as Error).message}</span> : null}
          {found.data && hits.length === 0 ? <span className="px-3 py-2 text-meta text-muted-foreground">Nothing you can see matches.</span> : null}
          {hits.length > 0 ? (
            <ul aria-label="Search results" className="m-0 flex list-none flex-col p-0">
              {hits.map((h) => (
                <li key={`${h.kind}-${h.id}`}>
                  <Link to={`${HIT_PATH[h.kind]}?open=${h.id}`} onClick={() => setOpen(false)} className={ROW}>
                    <span className="text-ui font-bold">{h.label}</span>
                    <span className="text-meta text-muted-foreground">{h.kind === 'member' ? 'Member' : 'Aspirant'} · {h.detail}</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

const NOTES: Record<string, { text: (n: number) => string; to: string }> = {
  pending_members: { text: (n) => `${plural(n, 'membership application', 'membership applications')} to verify`, to: '/party/members?status=pending' },
  submitted_aspirants: { text: (n) => `${plural(n, 'nomination', 'nominations')} submitted for vetting`, to: '/party/aspirants?status=submitted' },
}

/** What waits on the caller's offices, with a count on the bell. */
function Notifications() {
  const { open, setOpen, ref } = usePanel()
  const notes = ((usePartyNotifications().data || []) as { key: string; count: number }[]).filter((n) => n.count > 0 && NOTES[n.key])
  const total = notes.reduce((s, n) => s + n.count, 0)
  return (
    <div ref={ref} className="relative">
      <button type="button" aria-expanded={open} aria-controls="party-notifications" onClick={() => setOpen(!open)} className={ICON_BUTTON}
        aria-label={total ? `Notifications, ${total} waiting` : 'Notifications, nothing waiting'}>
        <Bell className="size-5" aria-hidden />
        {total ? <span aria-hidden className="absolute top-1 right-1 flex min-w-[18px] items-center justify-center rounded-full bg-destructive px-1 text-[11px] font-bold text-white">{total > 99 ? '99+' : total}</span> : null}
      </button>
      {open ? (
        <div id="party-notifications" className={PANEL}>
          {notes.length === 0 ? <span className="px-3 py-2 text-ui text-muted-foreground">Nothing needs you right now.</span> : null}
          {notes.map((n) => (
            <Link key={n.key} to={NOTES[n.key].to} onClick={() => setOpen(false)} className={ROW}>
              <span className="text-ui font-semibold">{NOTES[n.key].text(n.count)}</span>
            </Link>
          ))}
        </div>
      ) : null}
    </div>
  )
}

/** Who to contact at the office. */
function Help() {
  const { open, setOpen, ref } = usePanel()
  const copy = useCopy()
  const party = (useSite().data || {}) as { contact_phone?: string; contact_email?: string }
  return (
    <div ref={ref} className="relative">
      <button type="button" aria-expanded={open} aria-controls="party-help" aria-label="Help" onClick={() => setOpen(!open)} className={ICON_BUTTON}>
        <CircleHelp className="size-5" aria-hidden />
      </button>
      {open ? (
        <div id="party-help" className={PANEL}>
          <span className="px-3 pt-2 text-ui font-bold">Need help?</span>
          <span className="px-3 pb-1 text-meta text-muted-foreground">{copy.help}</span>
          {party.contact_phone ? <a href={`tel:${party.contact_phone}`} className={ROW}><span className="text-ui font-semibold">Call {party.contact_phone}</span></a> : null}
          {party.contact_email ? <a href={`mailto:${party.contact_email}`} className={ROW}><span className="text-ui font-semibold">Email {party.contact_email}</span></a> : null}
          {!party.contact_phone && !party.contact_email ? <span className="px-3 pb-2 text-meta text-muted-foreground">{copy.helpNoContacts}</span> : null}
        </div>
      ) : null}
    </div>
  )
}

/** The console's top bar tools: help, and in a party installation search and notifications. */
export function ConsoleTools() {
  const { aspirant } = useInstall()
  return (
    <>
      {aspirant ? null : <PartySearch />}
      {aspirant ? null : <Notifications />}
      <Help />
    </>
  )
}
