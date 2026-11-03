import * as React from 'react'
import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { Badge } from './badge'

/** Website section head: tinted kicker pill + big display title + "see all" link on the right */
export function SectionHead({ kicker, title, action, onDark, className, rule }: { kicker?: string; title: React.ReactNode; action?: { label: string; to: string }; onDark?: boolean; className?: string; rule?: boolean }) {
  return (
    <div className={cn('flex flex-wrap items-end justify-between gap-4', rule && 'rule-top', className)}>
      <div className="flex flex-col">
        {kicker ? <Badge kind="kicker" tone={onDark ? 'gold' : 'tint'} className="mb-3 self-start">{kicker}</Badge> : null}
        <h2 className={cn('font-display font-extrabold tracking-[-0.02em]', rule ? 'text-[26px]' : 'text-section')}>{title}</h2>
      </div>
      {action ? <Link to={action.to} className={cn('font-bold', onDark && 'text-accent hover:text-accent')}>{action.label} →</Link> : null}
    </div>
  )
}

/** Small uppercase rail heading used in sidebars ("LATEST", "MOST READ") */
export function RailHead({ className, accent, ...props }: React.HTMLAttributes<HTMLHeadingElement> & { accent?: boolean }) {
  return <h2 className={cn('mb-2 text-ui font-extrabold uppercase tracking-[0.12em]', accent && 'border-t-[3px] border-primary pt-3', className)} {...props} />
}

/** Breadcrumb trail above inner-page titles */
export function Crumbs({ items, onDark }: { items: { label: string; to?: string }[]; onDark?: boolean }) {
  return (
    <nav aria-label="Breadcrumb" className={cn('text-ui', onDark ? 'text-on-dark-muted' : 'text-muted-foreground')}>
      {items.map((it, i) => (
        <span key={i}>
          {i > 0 ? ' / ' : ''}
          {it.to ? <Link to={it.to} className={onDark ? 'text-on-dark-muted' : 'text-muted-foreground'}>{it.label}</Link> : <span>{it.label}</span>}
        </span>
      ))}
    </nav>
  )
}

/** Story card meta: LABEL · place, then date · read time */
export function StoryMeta({ category, place }: { category: string; place?: string }) {
  return <span className="text-meta font-extrabold uppercase tracking-[0.08em] text-primary">{category}{place ? ` · ${place}` : ''}</span>
}
