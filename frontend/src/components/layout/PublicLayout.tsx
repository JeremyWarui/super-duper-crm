import * as React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { SiteHeader, SiteUtilityBar } from './SiteHeader'
import { SiteFooter } from './SiteFooter'
import { useCopy } from '@/copy'
import { useInstall } from '@/app/site'

/** True once the window has scrolled down from the top. */
function useScrolled() {
  const [scrolled, setScrolled] = React.useState(false)
  React.useEffect(() => {
    const check = () => setScrolled(window.scrollY > 8)
    check()
    window.addEventListener('scroll', check, { passive: true })
    return () => window.removeEventListener('scroll', check)
  }, [])
  return scrolled
}

/** Website frame: utility bar, sticky header, page, footer, and the phone-only Contribute and join bar. */
export function PublicLayout({ children }: { children: React.ReactNode }) {
  const { pathname, hash } = useLocation()
  const copy = useCopy()
  const install = useInstall()
  const isJoin = pathname.startsWith('/join') || pathname === copy.join.to
  const scrolled = useScrolled()
  // A new page opens at its top; a link to a section on it keeps its place.
  React.useEffect(() => {
    if (!hash) window.scrollTo(0, 0)
  }, [pathname, hash])
  // The frame waits for the site settings, so the names and colours never flash.
  if (install.loading) return null
  return (
    <div className="flex min-h-dvh flex-col bg-background">
      <SiteUtilityBar />
      <div className="site-sticky sticky top-0 z-30" data-scrolled={scrolled}>
        <SiteHeader />
      </div>
      <main id="main" key={pathname} className="page-in flex-1">{children}</main>
      <SiteFooter newsletter={!isJoin} />
      {!isJoin ? (
        <div className="sticky bottom-0 z-30 flex gap-2.5 border-t border-black/[0.06] bg-white/90 px-4 py-3 backdrop-blur-md md:hidden">
          <Button asChild variant="outline" className="flex-1"><Link to="/contribute">Contribute</Link></Button>
          <Button asChild variant="accent" className="flex-1"><Link to={copy.join.to}>{copy.join.label}</Link></Button>
        </div>
      ) : null}
    </div>
  )
}
