import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { Logo } from './Logo'

export type NavItem = { label: string; to: string }

export const crmNav: NavItem[] = [
  { label: 'Overview', to: '/crm' },
  { label: 'Members', to: '/crm/members' },
  { label: 'Branches', to: '/crm/branches' },
  { label: 'Events', to: '/crm/events' },
  { label: 'Nominations', to: '/crm/nominations' },
  { label: 'Nominees board', to: '/crm/nominees' },
  { label: 'Communications', to: '/crm/comms' },
  { label: 'Finance', to: '/crm/finance' },
  { label: 'Website content', to: '/crm/content' },
  { label: 'Users & data', to: '/crm/users' },
]

export const workspaceNav: NavItem[] = [
  { label: 'Strategy', to: '/ws' },
  { label: 'Targets & wards', to: '/ws/targets' },
  { label: 'Events', to: '/ws/events' },
  { label: 'Mobilizers', to: '/ws/mobilizers' },
  { label: 'Supporters', to: '/ws/supporters' },
  { label: 'Messages', to: '/ws/messages' },
  { label: 'Party feed & sharing', to: '/ws/party' },
  { label: 'Election-day agents', to: '/ws/agents' },
  { label: 'Spending', to: '/ws/spending' },
]

/**
 * 240px sidebar.
 * tone="dark"  — Party CRM: ink background, active item = solid party green, white text
 * tone="light" — Candidate workspace: white background, active item = green tint, green text
 * Items: 11px/12px padding, 10px corners, 15px semibold.
 */
export function AppSidebar({ items, tone = 'dark', title, subtitle, eyebrow, open }: { items: NavItem[]; tone?: 'dark' | 'light'; title?: string; subtitle?: string; eyebrow?: string; open?: boolean }) {
  const dark = tone === 'dark'
  return (
    <nav
      aria-label={dark ? 'Party CRM' : 'Workspace'}
      className={cn(
        'box-border flex-col gap-5 px-4 py-6 fixed inset-y-0 left-0 z-50 w-[280px] overflow-y-auto md:sticky md:top-0 md:z-auto md:flex md:h-dvh md:w-sidebar md:shrink-0',
        open ? 'flex' : 'hidden',
        dark ? 'bg-sidebar text-sidebar-foreground' : 'border-r border-line bg-white text-ink',
      )}
    >
      <div className="px-2">
        {dark ? (
          <div className="flex flex-col gap-0.5">
            <Logo size="sm" onDark to="/crm" />
            {subtitle ? <span className="pl-[44px] text-meta text-[#9FAAA4]">{subtitle}</span> : null}
          </div>
        ) : (
          <div className="flex flex-col gap-0.5">
            {eyebrow ? <span className="text-meta font-bold uppercase tracking-[0.1em] text-primary">{eyebrow}</span> : null}
            {title ? <span className="font-display text-[19px] font-extrabold">{title}</span> : null}
            {subtitle ? <span className="text-small text-muted-foreground">{subtitle}</span> : null}
          </div>
        )}
      </div>
      <div className="flex flex-col gap-0.5">
        {items.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end
            className={({ isActive }) =>
              cn(
                'block rounded-md px-3 py-[11px] text-body font-semibold no-underline',
                dark
                  ? isActive ? 'bg-sidebar-primary text-sidebar-primary-foreground hover:text-white' : 'text-sidebar-foreground hover:bg-sidebar-accent hover:text-white'
                  : isActive ? 'bg-primary-tint text-primary hover:text-primary' : 'text-text-2 hover:bg-stone hover:text-ink',
              )
            }
          >
            {n.label}
          </NavLink>
        ))}
      </div>
      <p className={cn('mx-2 mt-auto text-meta', dark ? 'text-[#9FAAA4]' : 'text-muted-foreground')}>Powered by [Your product]</p>
    </nav>
  )
}
