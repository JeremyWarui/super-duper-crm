import * as React from 'react'
import { Link } from 'react-router-dom'
import { useSite, useSubscribe } from '@/api/hooks'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useBranding } from '@/theme/branding'
import { useCopy } from '@/copy'
import { Logo } from './Logo'


/** The green band's SMS or email sign-up; the consent box carries the wording the server records. */
function Newsletter({ wording }: { wording: string }) {
  const copy = useCopy()
  const subscribe = useSubscribe()
  const [contact, setContact] = React.useState('')
  const [consent, setConsent] = React.useState(false)
  const done: any = subscribe.data
  return (
    <section aria-labelledby="ft-sub-h" className="bg-primary text-white">
      <div className="site-container flex flex-wrap items-center justify-between gap-5 py-11">
        <div className="flex max-w-[520px] flex-col gap-1.5">
          <h2 id="ft-sub-h" className="font-display text-[28px] font-extrabold">{copy.newsTitle}</h2>
          <p className="text-[#CFE0D5]">{copy.newsLead}</p>
        </div>
        {done ? (
          <div role="status" className="flex max-w-[420px] flex-col gap-1.5">
            <span className="font-bold">{done.message}</span>
            <Link to={done.unsubscribe_url} className="text-small text-white underline hover:text-white">Keep this unsubscribe link</Link>
          </div>
        ) : (
          <form
            className="flex max-w-[460px] flex-col gap-2"
            onSubmit={(e) => { e.preventDefault(); subscribe.mutate({ contact, consent_given: consent }) }}
          >
            <div className="flex flex-wrap gap-2.5">
              <label className="flex flex-col gap-1 text-small font-semibold">
                Phone or email
                <Input size="lg" required value={contact} onChange={(e) => setContact(e.target.value)} placeholder="07XX… or name@mail.com" className="min-w-[260px] border-0" />
              </label>
              <Button type="submit" variant="accent" shape="rounded" disabled={subscribe.isPending} className="h-[50px] self-end px-6 text-base">Subscribe</Button>
            </div>
            <label className="flex items-start gap-2 text-meta text-[#CFE0D5]">
              <input type="checkbox" required checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-0.5 size-4 accent-accent" />
              <span>{wording} See the <Link to="/privacy" className="text-white hover:text-white">privacy notice</Link>.</span>
            </label>
            {subscribe.error ? <span role="alert" className="text-small font-semibold text-accent">{(subscribe.error as Error).message}</span> : null}
          </form>
        )}
      </div>
    </section>
  )
}

/** Shared website footer: news sign-up, the site's contacts and socials, link columns, legal row. */
export function SiteFooter({ newsletter = true }: { newsletter?: boolean }) {
  const b = useBranding()
  const copy = useCopy()
  const party: any = useSite().data
  const socials = Object.entries(party?.social_links || {}) as [string, string][]
  const contact = [party?.contact_phone, party?.contact_email].filter(Boolean)
  return (
    <div className="w-full">
      {newsletter && party ? <Newsletter wording={party.subscribe_consent_wording} /> : null}
      <footer className="bg-ink text-on-dark-muted">
        <div className="site-container flex flex-col gap-8 pt-14 pb-6">
          <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-7 text-body">
            <div className="flex flex-col gap-2.5">
              <Logo size="md" onDark />
              {party?.address ? <span>{party.address}</span> : null}
              {contact.length ? <span>{contact.join(' · ')}</span> : null}
              {socials.length ? (
                <span className="flex flex-wrap gap-x-3.5 gap-y-2 pt-1">
                  {socials.map(([name, url]) => <a key={name} href={url} target="_blank" rel="noreferrer" className="text-ui font-semibold text-on-dark hover:text-white">{name}</a>)}
                </span>
              ) : null}
            </div>
            {copy.footer.map((c) => (
              <div key={c.title} className="flex flex-col gap-2.5">
                <span className="font-bold text-on-dark">{c.title}</span>
                {c.links.map(([label, to]: string[]) => <Link key={label} to={to} className="py-0.5 text-on-dark-muted hover:text-white">{label}</Link>)}
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1.5 border-t border-ink-2 pt-[18px] text-small">
            <span>© {new Date().getFullYear()} {b.partyName}{b.registrationNo ? ` · Reg. No. ${b.registrationNo}` : ''}</span>
            <Link to="/privacy" className="text-on-dark-muted hover:text-white">Privacy notice</Link>
            <Link to="/privacy#data-protection" className="text-on-dark-muted hover:text-white">Data protection</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
