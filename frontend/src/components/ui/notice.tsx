import * as React from 'react'
import { cn } from '@/lib/utils'

/** The amber box for something to know before acting: practice mode, a pending step, a failed send. */
export function Notice({ role = 'note', className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div role={role} className={cn('rounded-lg border border-warn-line bg-warn px-4 py-3 text-ui text-warn-foreground', className)} {...props} />
}

/** The green line that says an action worked; `boxed` sets it on a tinted panel. */
export function StatusText({ boxed, className, ...props }: React.HTMLAttributes<HTMLParagraphElement> & { boxed?: boolean }) {
  return <p role="status" className={cn('font-semibold text-primary', boxed ? 'rounded-lg bg-primary-tint p-4' : 'text-ui', className)} {...props} />
}
