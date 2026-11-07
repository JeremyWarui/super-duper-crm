import * as React from 'react'
import { NavLink } from 'react-router-dom'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Logo } from './Logo'

export type NavItem = { label: string; to: string; icon?: LucideIcon }
export type NavGroup = { label: string; items: NavItem[] }

const itemClass = (dark: boolean) => ({ isActive }: { isActive: boolean }) =>
  cn(
    'flex min-h-[42px] items-center gap-2.5 rounded-md px-3 text-body font-semibold no-underline',
    dark
      ? isActive ? 'bg-sidebar-primary text-sidebar-primary-foreground hover:text-white' : 'text-sidebar-foreground hover:bg-sidebar-accent hover:text-white'
      : isActive ? 'bg-primary-tint font-bold text-primary hover:text-primary' : 'text-text-2 hover:bg-stone hover:text-ink',
  )

function Items({ items, dark }: { items: NavItem[]; dark: boolean }) {
  return (
    <>
      {items.map(({ to, label, icon: Icon }) => (
        <NavLink key={to} to={to} className={itemClass(dark)}>
          {Icon ? <Icon className="size-[18px] shrink-0" strokeWidth={2} aria-hidden /> : null}
          {label}
        </NavLink>
      ))}
    </>
  )
}

/**
 * 240px sidebar; a slide-in drawer on phones.
 * tone="dark": the party console, a flat list on ink.
 * tone="light": a campaign workspace, with a brand, a card, grouped items with icons and a footer.
 */
export function AppSidebar({ items = [], groups, tone = 'dark', label, title, subtitle, eyebrow, home, open, brand, card, footer }: {
  items?: NavItem[]
  groups?: NavGroup[]
  tone?: 'dark' | 'light'
  /** The dark sidebar's name for screen readers. */
  label?: string
  title?: string
  subtitle?: string
  eyebrow?: string
  home: string
  open?: boolean
  brand?: React.ReactNode
  card?: React.ReactNode
  footer?: React.ReactNode
}) {
  const dark = tone === 'dark'
  return (
    <nav
      aria-label={dark ? label : 'Workspace'}
      className={cn(
        'box-border flex-col gap-[18px] px-3.5 py-[22px] fixed inset-y-0 left-0 z-50 w-[280px] overflow-y-auto md:sticky md:top-0 md:z-auto md:flex md:h-dvh md:w-sidebar md:shrink-0',
        open ? 'flex' : 'hidden',
        dark ? 'bg-sidebar text-sidebar-foreground' : 'border-r border-line bg-white text-ink',
      )}
    >
      <div className="px-2">
        {dark ? (
          <div className="flex flex-col gap-0.5">
            <Logo size="sm" onDark to={home} />
            {subtitle ? <span className="pl-[44px] text-meta text-[#9FAAA4]">{subtitle}</span> : null}
          </div>
        ) : brand ?? (
          <div className="flex flex-col gap-0.5">
            {eyebrow ? <span className="text-meta font-bold uppercase tracking-[0.1em] text-primary">{eyebrow}</span> : null}
            {title ? <span className="font-display text-[19px] font-extrabold">{title}</span> : null}
            {subtitle ? <span className="text-small text-muted-foreground">{subtitle}</span> : null}
          </div>
        )}
      </div>
      {card}
      {groups ? (
        <div className="flex flex-col gap-3.5">
          {groups.map((g) => (
            <div key={g.label} role="group" aria-label={g.label} className="flex flex-col gap-0.5">
              <span aria-hidden className="px-3 pb-1 text-meta font-bold uppercase tracking-[0.08em] text-muted-foreground">{g.label}</span>
              <Items items={g.items} dark={dark} />
            </div>
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-0.5">
          <Items items={items} dark={dark} />
        </div>
      )}
      {footer ? <div className="mt-auto flex flex-col gap-2 border-t border-line-soft px-2 pt-3">{footer}</div> : null}
    </nav>
  )
}
