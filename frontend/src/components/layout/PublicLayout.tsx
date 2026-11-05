import * as React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { SiteHeader, SiteUtilityBar } from './SiteHeader'
import { SiteFooter } from './SiteFooter'
import { useCopy } from '@/copy'
import { useInstall } from '@/app/site'

/** Website frame: utility bar, sticky header, page, footer, and the phone-only Contribute and join bar. */
export function PublicLayout({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation()
  const copy = useCopy()
  const install = useInstall()
  const isJoin = pathname.startsWith('/join') || pathname === copy.join.to
  // The words differ by installation, so the frame waits until it knows which this is.
  if (install.loading) return null
  return (
    <div className="flex min-h-dvh flex-col bg-background">
      <SiteUtilityBar />
      <div className="sticky top-0 z-30">
        <SiteHeader />
      </div>
      <main id="main" className="flex-1">{children}</main>
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
