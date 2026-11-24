import * as React from 'react'
import { Link } from 'react-router-dom'
import { Bell, CircleHelp } from 'lucide-react'
import { useSite } from '@/api/hooks'
import { usePanel } from '@/lib/usePanel'
import { cn } from '@/lib/utils'
import { formatDateTime } from '@/lib/format'

export const PANEL = 'absolute right-0 z-50 mt-2 flex w-[min(92vw,380px)] flex-col gap-1 rounded-photo border border-line bg-white p-2 shadow-pop'
const ICON_BUTTON = 'relative flex size-11 cursor-pointer items-center justify-center rounded-full hover:bg-stone'
const ROW = 'flex min-h-11 flex-col justify-center rounded-lg px-3 py-1.5 text-ink no-underline hover:bg-stone'

export type Hit = { key: string; to: string; label: string; detail: string }
export type Note = { key: string; to: string; text: string; detail?: string; sender?: string; at?: string; read?: boolean }

/** One note: its text, a preview line, and who sent it when. */
export function NoteBody({ note }: { note: Note }) {
  const meta = [note.sender, note.at ? formatDateTime(note.at) : ''].filter(Boolean).join(' · ')
  return (
    <>
      <span className="text-ui font-semibold">{note.text}</span>
      {note.detail ? <span className="line-clamp-2 text-meta text-ink">{note.detail}</span> : null}
      {meta ? <span className="text-meta text-muted-foreground">{meta}</span> : null}
    </>
  )
}

/** Runs `fn` on Ctrl K or Cmd K anywhere on the page. */
export function useHotkeyK(fn: () => void) {
  const latest = React.useRef(fn)
  React.useEffect(() => { latest.current = fn })
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); latest.current() }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])
}

/** Search results as links; picking one calls `onPick`. */
export function HitList({ hits, onPick }: { hits: Hit[]; onPick: () => void }) {
  return (
    <ul aria-label="Search results" className="m-0 flex list-none flex-col p-0">
      {hits.map((h) => (
        <li key={h.key}>
          <Link to={h.to} onClick={onPick} className={ROW}>
            <span className="text-ui font-bold">{h.label}</span>
            <span className="text-meta text-muted-foreground">{h.detail}</span>
          </Link>
        </li>
      ))}
    </ul>
  )
}

/**
 * The bell: `count` on its badge, read out as "`count` `word`". It opens a panel of `notes` linking
 * to their pages; with `page`, a phone goes to that page instead and the panel links to it.
 */
export function BellPanel({ id, notes, todo = [], count, word, page }: { id: string; notes: Note[]; todo?: Note[]; count: number; word: string; page?: string }) {
  const { open, setOpen, ref } = usePanel()
  const label = count ? `Notifications, ${count} ${word}` : `Notifications, nothing ${word}`
  const badge = count ? <span aria-hidden className="absolute top-1 right-1 flex min-w-[18px] items-center justify-center rounded-full bg-destructive px-1 text-[11px] font-bold text-white">{count > 99 ? '99+' : count}</span> : null
  return (
    <div ref={ref} className="relative">
      {page ? (
        <Link to={page} aria-label={label} className={cn(ICON_BUTTON, 'text-ink sm:hidden')}>
          <Bell className="size-5" aria-hidden />
          {badge}
        </Link>
      ) : null}
      <button type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)} className={cn(ICON_BUTTON, page && 'max-sm:hidden')} aria-label={label}>
        <Bell className="size-5" aria-hidden />
        {badge}
      </button>
      {open ? (
        <div id={id} role="region" aria-label="Notifications" className={PANEL}>
          {notes.length === 0 && todo.length === 0 ? <span className="px-3 py-2 text-ui text-muted-foreground">Nothing new.</span> : null}
          {notes.length ? (
            <ul aria-label="New" className="m-0 flex list-none flex-col p-0">
              {notes.map((n) => <li key={n.key}><Link to={n.to} onClick={() => setOpen(false)} className={ROW}><NoteBody note={n} /></Link></li>)}
            </ul>
          ) : null}
          {todo.length ? (
            <>
              <span className="px-3 pt-2 text-meta font-bold uppercase tracking-wide text-muted-foreground">To do</span>
              <ul aria-label="To do" className="m-0 flex list-none flex-col p-0">
                {todo.map((n) => <li key={n.key}><Link to={n.to} onClick={() => setOpen(false)} className={ROW}><NoteBody note={n} /></Link></li>)}
              </ul>
            </>
          ) : null}
          {page ? <Link to={page} onClick={() => setOpen(false)} className="mt-1 border-t border-line-soft px-3 pt-2.5 pb-1.5 text-ui font-bold">See all notifications</Link> : null}
        </div>
      ) : null}
    </div>
  )
}

/** Help: `lead`, then the site's call and email contacts, or `none` when it lists neither. */
export function HelpPanel({ id, lead, none }: { id: string; lead: string; none?: string }) {
  const { open, setOpen, ref } = usePanel()
  const site = (useSite().data || {}) as { contact_phone?: string; contact_email?: string }
  return (
    <div ref={ref} className="relative">
      <button type="button" aria-expanded={open} aria-controls={id} aria-label="Help" onClick={() => setOpen(!open)} className={ICON_BUTTON}>
        <CircleHelp className="size-5" aria-hidden />
      </button>
      {open ? (
        <div id={id} className={PANEL}>
          <span className="px-3 pt-2 text-ui font-bold">Need help?</span>
          <span className="px-3 pb-1 text-meta text-muted-foreground">{lead}</span>
          {site.contact_phone ? <a href={`tel:${site.contact_phone}`} className={ROW}><span className="text-ui font-semibold">Call {site.contact_phone}</span></a> : null}
          {site.contact_email ? <a href={`mailto:${site.contact_email}`} className={ROW}><span className="text-ui font-semibold">Email {site.contact_email}</span></a> : null}
          {none && !site.contact_phone && !site.contact_email ? <span className="px-3 pb-2 text-meta text-muted-foreground">{none}</span> : null}
        </div>
      ) : null}
    </div>
  )
}
