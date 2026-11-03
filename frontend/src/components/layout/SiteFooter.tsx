import * as React from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useBranding } from '@/theme/branding'
import { Logo } from './Logo'

const cols = [
  { title: 'The party', links: [['About & history', '/about'], ['Leadership', '/about#leadership'], ['Constitution & rules', '/about#documents'], ['Agenda & issues', '/issues']] },
  { title: 'Take part', links: [['Join the party', '/join'], ['Find your branch', '/counties'], ['Events', '/events'], ['Become an aspirant', '/aspirants/apply']] },
  { title: 'Media', links: [['News & statements', '/news'], ['Primary results', '/results'], ['Photos & video', '/news?section=video'], ['Press kit', '/news#press']] },
  { title: 'Accounts', links: [['Member sign in', '/sign-in'], ['Staff & volunteer sign in', '/sign-in?staff=1'], ['Contribute', '/#contribute'], ['Contact us', '/about#contact']] },
] as const

/** Shared website footer (mockup: SiteFooter). newsletter={false} hides the green sign-up band (Join page). */
export function SiteFooter({ newsletter = true }: { newsletter?: boolean }) {
  const b = useBranding()
  const [done, setDone] = React.useState(false)
  return (
    <div className="w-full">
      {newsletter ? (
        <section aria-labelledby="ft-sub-h" className="bg-primary text-white">
          <div className="site-container flex flex-wrap items-center justify-between gap-5 py-11">
            <div className="flex max-w-[520px] flex-col gap-1.5">
              <h2 id="ft-sub-h" className="font-display text-[28px] font-extrabold">Get party news by SMS or email</h2>
              <p className="text-[#CFE0D5]">Statements, events near you and nomination notices. Unsubscribe any time; reply STOP to SMS.</p>
            </div>
            <form className="flex flex-col gap-2" onSubmit={(e) => { e.preventDefault(); setDone(true) }}>
              <div className="flex flex-wrap gap-2.5">
                <label className="flex flex-col gap-1 text-small font-semibold">
                  Phone or email
                  <Input size="lg" placeholder="07XX… or name@mail.com" className="min-w-[260px] border-0" />
                </label>
                <Button type="submit" variant="accent" shape="rounded" className="h-[50px] self-end px-6 text-base">{done ? 'Subscribed ✓' : 'Subscribe'}</Button>
              </div>
              <span className="text-meta text-[#CFE0D5]">By subscribing you agree to receive party updates under our <Link to="/privacy" className="text-white hover:text-white">privacy notice</Link>.</span>
            </form>
          </div>
        </section>
      ) : null}
      <footer className="bg-ink text-on-dark-muted">
        <div className="site-container flex flex-col gap-8 pt-14 pb-6">
          <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-7 text-body">
            <div className="flex flex-col gap-2.5">
              <Logo size="md" onDark />
              <span>[Party headquarters address]</span>
              <span>[Phone] · [Email]</span>
              <span className="flex flex-wrap gap-x-3.5 gap-y-2 pt-1">
                {['Facebook', 'X', 'YouTube', 'TikTok'].map((s) => <a key={s} href="#" className="text-ui font-semibold text-on-dark hover:text-white">{s}</a>)}
              </span>
            </div>
            {cols.map((c) => (
              <div key={c.title} className="flex flex-col gap-2.5">
                <span className="font-bold text-on-dark">{c.title}</span>
                {c.links.map(([label, to]) => <Link key={label} to={to} className="py-0.5 text-on-dark-muted hover:text-white">{label}</Link>)}
              </div>
            ))}
          </div>
          <div className="flex flex-wrap justify-between gap-x-6 gap-y-2.5 border-t border-ink-2 pt-[18px] text-small">
            <span className="flex flex-wrap gap-x-4 gap-y-1.5">
              <span>© {new Date().getFullYear()} {b.partyName} · Reg. No. {b.registrationNo}</span>
              <Link to="/privacy" className="text-on-dark-muted hover:text-white">Privacy notice</Link>
              <Link to="/privacy#odpc" className="text-on-dark-muted hover:text-white">Data protection · ODPC Reg. [000]</Link>
              <Link to="/about#contributions" className="text-on-dark-muted hover:text-white">Contributions disclosure</Link>
              <Link to="/accessibility" className="text-on-dark-muted hover:text-white">Accessibility</Link>
            </span>
            <span>Powered by [Your product]</span>
          </div>
        </div>
      </footer>
    </div>
  )
}
