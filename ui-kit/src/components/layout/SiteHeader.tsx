import * as React from 'react'
import { NavLink, Link, useLocation } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { useBranding } from '@/theme/branding'
import { Logo } from './Logo'

export const siteNav = [
  { label: 'About', to: '/about' },
  { label: 'Agenda & issues', to: '/issues' },
  { label: 'News', to: '/news' },
  { label: 'Events', to: '/events' },
  { label: 'Candidates', to: '/candidates' },
  { label: 'Results', to: '/results' },
  { label: 'Counties', to: '/counties' },
] as const

type Lang = 'en' | 'sw'

/** Dark 13px utility bar above the header. Scrolls away; only the white header stays pinned. */
export function SiteUtilityBar({ lang, onLang, signedInName }: { lang: Lang; onLang: (l: Lang) => void; signedInName?: string | null }) {
  const b = useBranding()
  const langBtn = (l: Lang) => cn('min-w-9 cursor-pointer rounded-sm px-2.5 py-1.5 text-meta font-bold', lang === l ? 'bg-accent text-ink' : 'bg-transparent text-[#E2E5E3]')
  return (
    <div className="bg-ink text-small text-[#C9CDCB]">
      <div className="site-container flex flex-wrap items-center justify-between gap-2 py-2">
        <span className="hidden sm:inline">Registered political party · Reg. No. {b.registrationNo} · Hotline {b.hotline}</span>
        <span className="sm:hidden">Hotline {b.hotline}</span>
        <div className="flex flex-wrap items-center gap-4">
          <div role="group" aria-label="Language" className="flex gap-0.5">
            <button type="button" aria-pressed={lang === 'en'} onClick={() => onLang('en')} className={langBtn('en')}>EN</button>
            <button type="button" aria-pressed={lang === 'sw'} onClick={() => onLang('sw')} className={langBtn('sw')}>SW</button>
          </div>
          {signedInName ? (
            <span className="flex items-center gap-3.5">
              <Link to="/account" className="py-2 font-semibold text-white hover:text-white">{signedInName} · My account</Link>
              <Link to="/sign-out" className="py-2 text-[#C9CDCB] hover:text-white">Sign out</Link>
            </span>
          ) : (
            <Link to="/sign-in" className="py-2 font-semibold text-white hover:text-white">Sign in</Link>
          )}
        </div>
      </div>
    </div>
  )
}

/**
 * Shared website header (mockup: SiteHeader): frosted white, pinned by the layout
 * (`sticky top-0 z-30`). Current page = soft green pill.
 * Below 1280px the menu folds into a "Menu" button; Join/Contribute move to the
 * phone action bar at the bottom of the screen.
 */
export function SiteHeader() {
  const [open, setOpen] = React.useState(false)
  const { pathname } = useLocation()
  React.useEffect(() => setOpen(false), [pathname])
  const link = ({ isActive }: { isActive: boolean }) => cn('rounded-full px-3.5 py-[9px] no-underline', isActive ? 'bg-primary-tint text-primary hover:text-primary' : 'text-ink hover:bg-stone hover:text-ink')
  return (
    <header className="border-b border-black/[0.06] bg-white/80 backdrop-blur-[14px] backdrop-saturate-[1.8]">
      <div className="site-container flex items-center justify-between gap-3.5 py-3.5">
        <Logo size="lg" withSlogan />
        <nav aria-label="Main" className="hidden flex-wrap gap-x-1 gap-y-0.5 text-body font-semibold xl:flex">
          {siteNav.map((n) => <NavLink key={n.to} to={n.to} className={link}>{n.label}</NavLink>)}
        </nav>
        <div className="hidden gap-2.5 md:flex">
          <Button asChild variant="outline"><Link to="/#contribute">Contribute</Link></Button>
          <Button asChild variant="accent"><Link to="/join">Join the party</Link></Button>
        </div>
        <Button variant="quiet" className="xl:hidden" aria-expanded={open} aria-controls="site-menu" onClick={() => setOpen(!open)}>
          {open ? <X className="size-4" /> : <Menu className="size-4" />}Menu
        </Button>
      </div>
      {open ? (
        <nav id="site-menu" aria-label="Main" className="site-container flex flex-col gap-1 pb-4 text-base font-semibold xl:hidden">
          {siteNav.map((n) => <NavLink key={n.to} to={n.to} className={({ isActive }) => cn(link({ isActive }), 'px-4 py-3')}>{n.label}</NavLink>)}
        </nav>
      ) : null}
    </header>
  )
}
