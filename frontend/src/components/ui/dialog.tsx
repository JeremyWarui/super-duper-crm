import * as React from 'react'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * Modal dialog on the browser's own <dialog>: it traps focus, closes on Escape and dims the page.
 * Rendered while open; `onClose` runs for Escape, the close button and a click on the backdrop.
 * While `locked`, Escape and the backdrop do nothing and only the close button closes it.
 */
export function Dialog({ title, description, onClose, locked, className, children }: {
  title: React.ReactNode
  description?: React.ReactNode
  onClose: () => void
  locked?: boolean
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
      onCancel={(e) => { e.preventDefault(); if (!locked) onClose() }}
      onClick={(e) => { if (e.target === ref.current && !locked) onClose() }}
      className={cn('m-auto w-[min(560px,calc(100vw-32px))] max-h-[calc(100dvh-32px)] overflow-y-auto rounded-photo border border-black/5 bg-popover p-0 text-ink shadow-pop backdrop:bg-ink/40', className)}
    >
      <div className="flex flex-col gap-4 p-6">
        <div className="flow-root">
          {/* Floated so only the title's first line makes room for it. */}
          <button type="button" aria-label="Close" onClick={onClose} className="float-right -mt-3 -mr-3 ml-2 flex size-11 cursor-pointer items-center justify-center rounded-full hover:bg-stone"><X className="size-5" /></button>
          <h2 id={`${id}-t`} className="font-display text-h3 font-extrabold">{title}</h2>
          {description ? <p className="mt-1 text-ui text-muted-foreground">{description}</p> : null}
        </div>
        {children}
      </div>
    </dialog>
  )
}
