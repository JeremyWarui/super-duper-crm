import { cn } from '@/lib/utils'
import { Spinner } from './spinner'

/** The muted "Loading…" line, with a spinner, that a page or panel shows while its data arrives. */
export function LoadingText({ children = 'Loading…', className }: { children?: string; className?: string }) {
  return (
    <p className={cn('flex items-center gap-2 text-muted-foreground', className)}>
      <Spinner />
      {children}
    </p>
  )
}
