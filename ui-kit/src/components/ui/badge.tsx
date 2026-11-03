import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

/**
 * status — 12px bold pills used in tables (Verified, Pending, Flagged…)
 * label  — square-ish category box on news ("STATEMENT")
 * kicker — tinted pill above homepage section titles ("FROM THE PARTY")
 */
const badgeVariants = cva('inline-flex items-center gap-1 whitespace-nowrap font-bold', {
  variants: {
    tone: {
      ok: 'bg-ok text-ok-foreground',
      warn: 'bg-warn text-warn-foreground',
      bad: 'bg-bad text-bad-foreground',
      info: 'bg-info text-info-foreground',
      primary: 'bg-primary text-primary-foreground',
      ink: 'bg-ink text-accent',
      tint: 'bg-primary-tint text-primary',
      gold: 'bg-accent/15 text-accent',
      stone: 'bg-stone text-ink',
    },
    kind: {
      status: 'text-meta px-2.5 py-[3px] rounded-full',
      label: 'text-meta uppercase tracking-[0.1em] font-extrabold px-2 py-1 rounded-sm',
      kicker: 'text-small uppercase tracking-[0.1em] px-3 py-1.5 rounded-full',
      chip: 'text-ui font-semibold px-3 py-1.5 rounded-full',
    },
  },
  defaultVariants: { tone: 'ok', kind: 'status' },
})

type BadgeProps = React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>

export function Badge({ className, tone, kind, ...props }: BadgeProps) {
  return <span data-slot="badge" className={cn(badgeVariants({ tone, kind }), className)} {...props} />
}

export { badgeVariants }
