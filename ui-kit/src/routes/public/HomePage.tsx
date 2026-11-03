import * as React from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Pause, Play } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { NativeSelect, Field } from '@/components/ui/input'
import { SectionHead, StoryMeta } from '@/components/ui/typography'
import { cn } from '@/lib/utils'

const slides = ['#2D5A72', '#3E6B57', '#5B5F7A', '#6E5A46']
const issues = ['Jobs & livelihoods', 'Health', 'Education & youth', 'Agriculture & food', 'Devolution', 'Governance & integrity']

/** Demo of the homepage hero, agenda and news band built only from kit parts. */
export function HomePage() {
  const [i, setI] = React.useState(0)
  const [playing, setPlaying] = React.useState(true)
  const [county, setCounty] = React.useState('')
  React.useEffect(() => {
    if (!playing) return
    const t = setInterval(() => setI((x) => (x + 1) % slides.length), 6000)
    return () => clearInterval(t)
  }, [playing])

  return (
    <>
      {/* Hero carousel — 560px, gradient overlay, find-your-branch card */}
      <section aria-roledescription="carousel" aria-label="Highlights" className="relative flex min-h-[560px] flex-col justify-center overflow-hidden text-white">
        <div aria-live="polite" className="absolute inset-0 transition-colors duration-[600ms]" style={{ backgroundColor: slides[i] }} />
        <div aria-hidden className="absolute inset-0 bg-[linear-gradient(90deg,rgba(8,18,13,.82)_0%,rgba(8,18,13,.55)_50%,rgba(8,18,13,.2)_100%)]" />
        <div className="site-container relative flex flex-wrap items-center justify-between gap-10 pt-12 pb-8 md:pt-16 md:pb-28">
          <div className="flex min-w-0 max-w-[680px] flex-col gap-[22px]">
            <p className="kicker text-accent">[Year] General Election</p>
            <h1 className="font-display text-hero font-extrabold tracking-[-0.03em]">One Kenya. Every ward. Together.</h1>
            <p className="max-w-[40ch] text-[19px] leading-[1.6] text-[#ECECE7]">[The party's core message in one or two sentences.]</p>
            <div className="flex flex-wrap gap-3 pt-1.5">
              <Button asChild variant="accent" size="lg"><Link to="/join">Join the party</Link></Button>
              <Button asChild variant="onDark" size="lg"><Link to="/issues">Read the manifesto</Link></Button>
            </div>
          </div>
          <Card asChild variant="elevated" className="w-full max-w-[360px] gap-3.5 rounded-[22px] text-ink shadow-hero-card"><aside aria-label="Find your branch">
            <h2 className="font-display text-[22px] font-extrabold">Find your branch</h2>
            <Field label="Your county">
              <NativeSelect size="lg" value={county} onChange={(e) => setCounty(e.target.value)}>
                <option value="">Choose a county</option>
                {['Nairobi', 'Mombasa', 'Kisumu', 'Nakuru', 'Embu'].map((c) => <option key={c}>{c}</option>)}
              </NativeSelect>
            </Field>
            <Button asChild shape="rounded" className="h-[50px] text-base"><Link to="/counties">{county ? `Go to the ${county} branch` : 'See all branches'}</Link></Button>
            <div className="flex flex-col border-t border-line-2">
              {[['Events near me', '/events'], ['Check my membership', '/sign-in'], ['Primary results', '/results']].map(([l, to]) => (
                <Link key={l} to={to} className="flex justify-between border-b border-line-soft py-3 font-semibold text-ink no-underline last:border-0 hover:text-primary">{l}<ArrowRight aria-hidden className="size-4" /></Link>
              ))}
            </div>
          </aside></Card>
        </div>
        <div className="relative pb-7 md:absolute md:inset-x-0 md:bottom-7 md:pb-0">
          <div className="site-container flex flex-wrap items-center gap-3">
            <button aria-label="Previous slide" onClick={() => setI((i + 3) % 4)} className="size-11 cursor-pointer rounded-full border-[1.5px] border-white/70 bg-black/20 text-lg">‹</button>
            <div role="group" aria-label="Choose slide" className="flex gap-1.5">
              {slides.map((_, k) => <button key={k} aria-label={`Slide ${k + 1}`} aria-current={k === i} onClick={() => setI(k)} className={cn('h-3 cursor-pointer rounded-full transition-all', k === i ? 'w-7 bg-accent' : 'w-3 bg-white/60')} />)}
            </div>
            <button aria-label="Next slide" onClick={() => setI((i + 1) % 4)} className="size-11 cursor-pointer rounded-full border-[1.5px] border-white/70 bg-black/20 text-lg">›</button>
            <button onClick={() => setPlaying(!playing)} className="flex h-9 cursor-pointer items-center gap-1.5 rounded-full border-[1.5px] border-white/70 bg-black/20 px-3.5 text-small font-bold">{playing ? <><Pause className="size-3.5" />Pause</> : <><Play className="size-3.5" />Play</>}</button>
          </div>
        </div>
      </section>

      {/* Agenda — white band, 6 equal tiles */}
      <section id="issues" className="bg-white">
        <div className="site-container flex flex-col gap-8 py-20">
          <SectionHead kicker="Our agenda" title="Where we stand" action={{ label: 'Download the manifesto (PDF)', to: '/issues' }} />
          <div className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-4">
            {issues.map((t, k) => (
              <Card key={t} asChild interactive className="gap-2.5 text-ink"><Link to="/issues">
                <span className="flex size-11 items-center justify-center rounded-lg bg-primary-tint font-display font-extrabold text-primary">{String(k + 1).padStart(2, '0')}</span>
                <span className="text-card-title font-bold">[{t}]</span>
                <span className="text-body text-muted-foreground">[One-line summary of the party's position.]</span>
                <span className="text-ui font-bold text-primary">Our position →</span>
              </Link></Card>
            ))}
          </div>
        </div>
      </section>

      {/* News band — warm stone */}
      <section id="news" className="bg-stone">
        <div className="site-container flex flex-col gap-7 py-20">
          <SectionHead kicker="From the party" title="News & statements" action={{ label: 'All news', to: '/news' }} />
          <div className="flex flex-wrap gap-7">
            <Link to="/news/1" className="flex min-w-0 flex-[3_1_460px] flex-col gap-3.5 text-ink no-underline hover:text-ink">
              <div className="ph aspect-video rounded-card">[Featured story photo]</div>
              <span className="flex items-center gap-2.5"><Badge kind="label" tone="primary">Statement</Badge><span className="text-meta font-extrabold uppercase tracking-[0.1em] text-muted-foreground">National · [0] hours ago</span></span>
              <span className="font-display text-[30px] font-extrabold leading-[1.15] tracking-[-0.01em]">[Headline of the party's lead story this week]</span>
              <span className="text-muted-foreground">[One-sentence summary of the story.]</span>
            </Link>
            <div className="flex min-w-0 flex-[2_1_320px] flex-col">
              {[['Statement', '[Party responds to …]'], ['Counties', '[County branch holds delegates meeting]'], ['Nominations', '[Aspirant applications now open]'], ['Opinion', '[Op-ed by party official]']].map(([c, t]) => (
                <Link key={t} to="/news/1" className="flex gap-4 border-b border-line-2 py-4 text-ink no-underline hover:text-ink">
                  <div className="ph h-[76px] w-[104px] shrink-0 rounded-lg" />
                  <div className="flex min-w-0 flex-col gap-1.5"><StoryMeta category={c} /><span className="font-bold leading-[1.35]">{t}</span><span className="text-small text-muted-foreground">[dd Mon] · [0] min read</span></div>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </section>
    </>
  )
}
