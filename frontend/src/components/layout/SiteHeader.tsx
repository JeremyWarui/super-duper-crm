import * as React from 'react'
import { NavLink, Link, useLocation } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { useBranding } from '@/theme/branding'
import { homeOf } from '@/lib/home'
import { useAuth } from '@/store/auth'
import { Logo } from './Logo'

export const siteNav = [
  { label: 'About', to: '/about' },
  { label: 'News', to: '/news' },
  { label: 'Events', to: '/events' },
  { label: 'Candidates', to: '/candidates' },
  { label: 'Results', to: '/results' },
  { label: 'Counties', to: '/counties' },
] as const

/** Dark 13px utility bar above the header: registration, hotline, and sign-in or the signed-in login. */
export function SiteUtilityBar() {
  const b = useBranding()
  const token = useAuth((s: any) => s.token)
  const user = useAuth((s: any) => s.user)
  const logout = useAuth((s: any) => s.logout)
  const facts = [b.registrationNo && `Reg. No. ${b.registrationNo}`, b.hotline && `Hotline ${b.hotline}`].filter(Boolean)
  return (
    <div className="bg-ink text-small text-[#C9CDCB]">
      <div className="site-container flex flex-wrap items-center justify-between gap-2 py-2">
        <span className="hidden sm:inline">{['Registered political party', ...facts].join(' · ')}</span>
        <span className="sm:hidden">{b.hotline ? `Hotline ${b.hotline}` : null}</span>
        {token ? (
          <span className="flex items-center gap-3.5">
            <Link to={user?.member_account ? "/account" : homeOf(user)} className="py-2 font-semibold text-white hover:text-white">{[(user?.full_name || '').split(' ')[0], 'My account'].filter(Boolean).join(' · ')}</Link>
            <button type="button" onClick={logout} className="cursor-pointer py-2 text-[#C9CDCB] hover:text-white">Sign out</button>
          </span>
        ) : (
          <Link to="/signin" className="py-2 font-semibold text-white hover:text-white">Sign in</Link>
        )}
      </div>
    </div>
  )
}

/**
 * Shared website header: frosted white, pinned by the layout. Current page = soft green pill.
 * Below 1280px the menu folds into a "Menu" button; Join and Contribute move to the phone action bar.
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
          <Button asChild variant="outline"><Link to="/contribute">Contribute</Link></Button>
          <Button asChild variant="accent"><Link to="/join-party">Join the party</Link></Button>
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
