import * as React from 'react'
import { cn } from '@/lib/utils'

/** The right-aligned row of buttons at the foot of a form or dialog; it wraps on a phone. */
export function FormActions({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn('flex flex-wrap items-center justify-end gap-2', className)}>{children}</div>
}
