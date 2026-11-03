import * as React from 'react'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * Modal dialog on the browser's own <dialog>: it traps focus, closes on Escape and dims the page.
 * Rendered while open; `onClose` runs for Escape, the close button and a click on the backdrop.
 */
export function Dialog({ title, description, onClose, className, children }: {
  title: React.ReactNode
  description?: React.ReactNode
  onClose: () => void
  className?: string
  children: React.ReactNode
}) {
  const ref = React.useRef<HTMLDialogElement>(null)
  React.useEffect(() => {
    const d = ref.current
    if (d && !d.open) {
      if (typeof d.showModal === 'function') d.showModal()
      else d.setAttribute('open', '')
    }
  }, [])
  const id = React.useId()
  return (
    <dialog
      ref={ref}
      aria-labelledby={`${id}-t`}
      onCancel={(e) => { e.preventDefault(); onClose() }}
      onClick={(e) => { if (e.target === ref.current) onClose() }}
      className={cn('m-auto w-[min(560px,calc(100vw-32px))] max-h-[calc(100dvh-32px)] overflow-y-auto rounded-photo border border-black/5 bg-popover p-0 text-ink shadow-pop backdrop:bg-ink/40', className)}
    >
      <div className="flex flex-col gap-4 p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <h2 id={`${id}-t`} className="font-display text-h3 font-extrabold">{title}</h2>
            {description ? <p className="text-ui text-muted-foreground">{description}</p> : null}
          </div>
          <button type="button" aria-label="Close" onClick={onClose} className="flex size-11 flex-none cursor-pointer items-center justify-center rounded-full hover:bg-stone"><X className="size-5" /></button>
        </div>
        {children}
      </div>
    </dialog>
  )
}
