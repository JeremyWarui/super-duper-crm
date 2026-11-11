import { cn } from '@/lib/utils'

/** The muted "Loading…" line a page or panel shows while its data arrives. */
export function LoadingText({ children = 'Loading…', className }: { children?: string; className?: string }) {
  return <p className={cn('text-muted-foreground', className)}>{children}</p>
}
