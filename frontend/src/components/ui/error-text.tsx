import { cn } from '@/lib/utils'

/** A failed request's message in red, or nothing when there is no error. Takes an Error or a string. */
export function ErrorText({ error, className }: { error?: { message: string } | string | null | false; className?: string }) {
  if (!error) return null
  return <p role="alert" className={cn('font-semibold text-destructive', className)}>{typeof error === 'string' ? error : error.message}</p>
}
