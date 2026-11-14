import { LoaderCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

/** A turning ring in the current text colour; decorative, so the words beside it carry the meaning. */
export function Spinner({ className }: { className?: string }) {
  return <LoaderCircle data-slot="spinner" aria-hidden className={cn('size-[1.1em] shrink-0 animate-spin', className)} />
}
