import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

/**
 * Inputs. Website forms use size="lg" (50px, 1.5px border, 12px corners).
 * CRM forms use size="md" (44px). Font is 16px so phones don't zoom in.
 */
const fieldVariants = cva(
  'w-full min-w-0 bg-white text-base font-normal text-foreground placeholder:text-faint rounded-lg border-[1.5px] border-input px-3.5 outline-none transition-colors focus-visible:border-primary focus-visible:outline-[3px] focus-visible:outline-primary/25 focus-visible:outline-offset-0 disabled:bg-stone disabled:opacity-50 aria-[invalid=true]:border-destructive',
  { variants: { size: { md: 'h-11', lg: 'h-[50px]' } }, defaultVariants: { size: 'md' } },
)

type InputProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size'> & VariantProps<typeof fieldVariants>

export function Input({ className, size, ...props }: InputProps) {
  return <input data-slot="input" className={cn(fieldVariants({ size }), className)} {...props} />
}

type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>
export function Textarea({ className, ...props }: TextareaProps) {
  return <textarea data-slot="textarea" className={cn(fieldVariants({ size: 'md' }), 'h-auto min-h-28 py-3 leading-relaxed', className)} {...props} />
}

/**
 * Native select on purpose: on phones the system picker is easier than a
 * custom drop-down for long lists (47 counties).
 */
type SelectProps = Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'size'> & VariantProps<typeof fieldVariants>
export function NativeSelect({ className, size, children, ...props }: SelectProps) {
  return (
    <select
      data-slot="select"
      className={cn(
        fieldVariants({ size }),
        'appearance-none font-medium pr-10 bg-[image:var(--select-chevron)] bg-no-repeat bg-[position:right_14px_center]',
        className,
      )}
      {...props}
    >
      {children}
    </select>
  )
}

/** A filter list named by `label`, whose blank first option reads `blank` and means no filter. `options` are { id, name } rows. */
export function FilterSelect({ label, value, onChange, options, blank, disabled, className }: {
  label: string
  value: string
  onChange: (value: string) => void
  options?: { id: string; name: string }[]
  blank: string
  disabled?: boolean
  className?: string
}) {
  return (
    <NativeSelect aria-label={label} className={cn('w-auto min-w-0 flex-[1_1_180px]', className)} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
      <option value="">{blank}</option>
      {(options || []).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
    </NativeSelect>
  )
}

/** Label stacked above its control, 13px semibold, 4–6px gap — as in every mockup form */
export function Field({ label, hint, className, children }: { label: React.ReactNode; hint?: React.ReactNode; className?: string; children: React.ReactNode }) {
  return (
    <label className={cn('flex flex-col gap-1.5 text-small font-semibold', className)}>
      <span>{label}</span>
      {children}
      {hint ? <span className="text-small font-normal text-muted-foreground">{hint}</span> : null}
    </label>
  )
}

export { fieldVariants }
