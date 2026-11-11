import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

/**
 * Card surfaces from the mockups.
 * elevated — website cards: white, hairline edge, soft shadow, 20px corners, 24px padding
 * outline  — CRM / workspace cards: white, 1px #E9E9E5 border, 16px corners, 24px padding
 * tile     — KPI tiles: like outline but 20px padding
 * tinted   — inner panels: #F7F7F5, 12px corners, 16px padding
 * ink      — feature panels: ink background, 20px corners, 24px padding
 * panel    — large website CTA panels: 24px corners, 32px padding (set the colour yourself)
 */
const cardVariants = cva('flex flex-col text-card-foreground', {
  variants: {
    variant: {
      elevated: 'bg-card border border-black/5 shadow-card rounded-card p-6 gap-3',
      outline: 'bg-card border border-line rounded-xl p-6 gap-4',
      tile: 'bg-card border border-line rounded-xl p-5 gap-1.5',
      tinted: 'bg-ground-app rounded-lg p-4 gap-1',
      ink: 'bg-ink text-on-dark rounded-card p-6 gap-3',
      panel: 'rounded-panel p-8 gap-3.5',
    },
    interactive: { true: 'no-underline text-inherit hover:text-inherit', false: '' },
  },
  compoundVariants: [{ variant: 'elevated', interactive: true, className: 'lift' }],
  defaultVariants: { variant: 'elevated', interactive: false },
})

type CardProps = React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof cardVariants> & { asChild?: boolean }

/** Use asChild to render as a link or section: <Card asChild interactive><Link to="…">…</Link></Card> */
export function Card({ className, variant, interactive, asChild, ...props }: CardProps) {
  const Comp = asChild ? Slot : 'div'
  return <Comp data-slot="card" className={cn(cardVariants({ variant, interactive }), className)} {...props} />
}

/** A card's heading: an h2, or the level given by `as`. */
export function CardTitle({ as: Tag = 'h2', className, ...props }: React.HTMLAttributes<HTMLHeadingElement> & { as?: 'h2' | 'h3' }) {
  return <Tag className={cn('text-card-title font-bold', className)} {...props} />
}
