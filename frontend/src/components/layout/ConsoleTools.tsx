import * as React from 'react'
import { Search } from 'lucide-react'
import { usePartyNotifications, usePartySearch } from '@/api/hooks'
import { useInstall } from '@/app/site'
import { useCopy } from '@/copy'
import { plural } from '@/lib/format'
import { usePanel } from '@/lib/usePanel'
import { BellPanel, HelpPanel, HitList, PANEL, useHotkeyK, type Note } from './TopBarTools'

const HIT_PATH: Record<string, string> = { member: '/party/members', aspirant: '/party/aspirants' }

type Found = { kind: 'member' | 'aspirant'; id: string; label: string; detail: string }

/** Search the registers the caller's offices open; Ctrl K or Cmd K opens it. */
function PartySearch() {
  const { open, setOpen, ref } = usePanel()
  const [q, setQ] = React.useState('')
  const found = usePartySearch(q)
  useHotkeyK(() => setOpen(true))
  const hits = ((found.data || []) as Found[]).map((h) => ({
    key: `${h.kind}-${h.id}`,
    to: `${HIT_PATH[h.kind]}?open=${h.id}`,
    label: h.label,
    detail: `${h.kind === 'member' ? 'Member' : 'Aspirant'} · ${h.detail}`,
  }))
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
          {hits.length > 0 ? <HitList hits={hits} onPick={() => setOpen(false)} /> : null}
        </div>
      ) : null}
    </div>
  )
}

const NOTES: Record<string, { text: (n: number) => string; to: string }> = {
  pending_members: { text: (n) => `${plural(n, 'membership application', 'membership applications')} to verify`, to: '/party/members?status=pending' },
  submitted_aspirants: { text: (n) => `${plural(n, 'nomination', 'nominations')} submitted for vetting`, to: '/party/aspirants?status=submitted' },
}

/** What waits on the caller's offices, with the total on the bell. */
function Notifications() {
  const waiting = ((usePartyNotifications().data || []) as { key: string; count: number }[]).filter((n) => n.count > 0 && NOTES[n.key])
  const notes: Note[] = waiting.map((n) => ({ key: n.key, to: NOTES[n.key].to, text: NOTES[n.key].text(n.count) }))
  const total = waiting.reduce((s, n) => s + n.count, 0)
  return <BellPanel id="party-notifications" notes={notes} count={total} word="waiting" />
}

/** The console's top bar tools: help, and in a party installation search and notifications. */
export function ConsoleTools() {
  const { aspirant } = useInstall()
  const copy = useCopy()
  return (
    <>
      {aspirant ? null : <PartySearch />}
      {aspirant ? null : <Notifications />}
      <HelpPanel id="party-help" lead={copy.help} none={copy.helpNoContacts} />
    </>
  )
}
