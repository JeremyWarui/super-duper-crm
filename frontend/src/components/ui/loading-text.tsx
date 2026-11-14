import { cn } from '@/lib/utils'
import { Spinner } from './spinner'

/** The muted "Loading…" line, spinner first, centred in the page or panel waiting for its data. */
export function LoadingText({ children = 'Loading…', className }: { children?: string; className?: string }) {
  return (
    <p className={cn('flex w-full items-center justify-center gap-2 py-8 text-muted-foreground', className)}>
      <Spinner />
      {children}
    </p>
  )
}
