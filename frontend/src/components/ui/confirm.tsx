import * as React from 'react'
import { Button } from '@/components/ui/button'
import { Field, Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

type Variant = React.ComponentProps<typeof Button>['variant']
type Size = React.ComponentProps<typeof Button>['size']

/**
 * A button that asks before it acts: `label` opens `question` with `yes` and `no`.
 * `onConfirm(close)` runs on yes; call `close()` to put the button back.
 */
export function Confirm({
  label, question, yes, no = 'Cancel', onConfirm, onAsk, pending, disabled, size, variant = 'danger', yesVariant = 'danger', ariaLabel, className,
}: {
  label: React.ReactNode
  question: React.ReactNode
  yes: React.ReactNode
  no?: string
  onConfirm: (close: () => void) => void
  onAsk?: () => void
  pending?: boolean
  disabled?: boolean
  size?: Size
  variant?: Variant
  yesVariant?: Variant
  ariaLabel?: string
  className?: string
}) {
  const [asking, setAsking] = React.useState(false)
  const close = () => setAsking(false)
  if (!asking) {
    return (
      <Button shape="rounded" size={size} variant={variant} disabled={disabled} aria-label={ariaLabel} className={className}
        onClick={() => { onAsk?.(); setAsking(true) }}>
        {label}
      </Button>
    )
  }
  return (
    <span className={cn('inline-flex flex-wrap items-center gap-2', className)}>
      <span className="text-ui font-semibold">{question}</span>
      <Button shape="rounded" size={size} variant={yesVariant} disabled={pending || disabled} onClick={() => onConfirm(close)}>{yes}</Button>
      <Button shape="rounded" size={size} variant="quiet" onClick={close}>{no}</Button>
    </span>
  )
}

/** A reason box with `yes` and `no` buttons; `yes` waits for at least `min` characters. */
export function ReasonForm({
  label, placeholder, value, onChange, min = 1, yes, no, busy, onYes, onNo, visibleLabel,
}: {
  label: string
  placeholder?: string
  value: string
  onChange: (v: string) => void
  min?: number
  yes: string
  no: string
  busy?: boolean
  onYes: () => void
  onNo: () => void
  visibleLabel?: boolean
}) {
  const input = <Input aria-label={visibleLabel ? undefined : label} placeholder={placeholder} value={value} onChange={(e) => onChange(e.target.value)} />
  return (
    <div className="flex flex-wrap items-end gap-2">
      {visibleLabel ? <Field label={label} className="min-w-0 flex-1">{input}</Field> : <div className="min-w-0 flex-1">{input}</div>}
      <Button shape="rounded" size="sm" variant="danger" disabled={busy || value.trim().length < min} onClick={onYes}>{yes}</Button>
      <Button shape="rounded" size="sm" variant="quiet" onClick={onNo}>{no}</Button>
    </div>
  )
}
