import * as React from 'react'
import * as TabsPrimitive from '@radix-ui/react-tabs'
import { cn } from '@/lib/utils'

/**
 * Two tab looks from the mockups:
 *  look="segmented" — pill buttons inside a white capsule (CRM filters, Members, Events)
 *  look="underline" — newspaper section bar (News sections), 3px green underline
 */
type Look = 'segmented' | 'underline'
const LookCtx = React.createContext<Look>('segmented')

export function Tabs({ look = 'segmented', className, ...props }: React.ComponentProps<typeof TabsPrimitive.Root> & { look?: Look }) {
  return (
    <LookCtx.Provider value={look}>
      <TabsPrimitive.Root data-slot="tabs" className={cn('flex flex-col gap-4', className)} {...props} />
    </LookCtx.Provider>
  )
}

export function TabsList({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.List>) {
  const look = React.useContext(LookCtx)
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      className={cn(
        look === 'segmented'
          ? 'inline-flex w-fit items-center rounded-full border border-line-control bg-white p-[3px]'
          : 'flex flex-wrap gap-x-[22px]',
        className,
      )}
      {...props}
    />
  )
}

export function TabsTrigger({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  const look = React.useContext(LookCtx)
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      className={cn(
        'cursor-pointer font-bold text-ink transition-colors',
        look === 'segmented'
          ? 'min-h-10 rounded-full px-4 text-ui data-[state=active]:bg-primary data-[state=active]:text-primary-foreground'
          : 'pt-4 pb-[13px] text-body data-[state=active]:text-primary data-[state=active]:shadow-[inset_0_-3px_0_var(--party-primary)]',
        className,
      )}
      {...props}
    />
  )
}

export function TabsContent({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return <TabsPrimitive.Content data-slot="tabs-content" className={cn('outline-none', className)} {...props} />
}

/** Same segmented look for plain filter buttons that aren't tabs (aria-pressed toggles) */
export function FilterPills<T extends string>({ options, value, onChange, label }: { options: readonly T[]; value: T; onChange: (v: T) => void; label: string }) {
  return (
    <div role="group" aria-label={label} className="inline-flex w-fit flex-wrap items-center rounded-full border border-line-control bg-white p-[3px]">
      {options.map((o) => (
        <button
          key={o}
          type="button"
          aria-pressed={o === value}
          onClick={() => onChange(o)}
          className={cn('min-h-10 cursor-pointer rounded-full px-4 text-ui font-bold max-sm:min-h-11', o === value ? 'bg-primary text-primary-foreground' : 'text-ink')}
        >
          {o}
        </button>
      ))}
    </div>
  )
}
