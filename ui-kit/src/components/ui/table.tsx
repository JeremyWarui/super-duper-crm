import * as React from 'react'
import { cn } from '@/lib/utils'

/** Data tables as in Members, Targets, Supporters, Tally. Wraps in a horizontal scroller for phones. */
export function Table({ className, minWidth = 600, ...props }: React.TableHTMLAttributes<HTMLTableElement> & { minWidth?: number }) {
  return (
    <div className="overflow-x-auto">
      <table data-slot="table" style={{ minWidth }} className={cn('w-full border-collapse text-body', className)} {...props} />
    </div>
  )
}
export function THead(props: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <thead {...props} />
}
export function TBody(props: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody {...props} />
}
export function TR({ className, selected, ...props }: React.HTMLAttributes<HTMLTableRowElement> & { selected?: boolean }) {
  return <tr aria-selected={selected || undefined} className={cn(selected && 'bg-[#F4F8F5]', className)} {...props} />
}
export function TH({ className, align, ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return <th scope="col" className={cn('px-3 py-2.5 text-left text-small font-semibold text-muted-foreground border-b border-line', align === 'right' && 'text-right', className)} {...props} />
}
export function TD({ className, align, numeric, ...props }: React.TdHTMLAttributes<HTMLTableCellElement> & { numeric?: boolean }) {
  return <td className={cn('p-3 border-b border-line-soft', (align === 'right' || numeric) && 'text-right', numeric && 'tabular-nums', className)} {...props} />
}
/** Row name that opens a detail panel: bold, underlined with a soft line */
export function RowButton({ className, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button type="button" className={cn('cursor-pointer bg-transparent py-1.5 text-left font-bold text-ink underline decoration-input underline-offset-[3px]', className)} {...props} />
}
