import * as React from 'react'
import { cn } from '@/lib/utils'

// Below 640px a stacked table drops its header and shows each row as a card, each cell
// labelled with its column's heading.
const STACK = [
  'max-sm:block max-sm:[&_thead]:hidden max-sm:[&_tbody]:block',
  'max-sm:[&_tr]:flex max-sm:[&_tr]:flex-col max-sm:[&_tr]:gap-1 max-sm:[&_tr]:border-b max-sm:[&_tr]:border-line-soft max-sm:[&_tr]:py-3',
  'max-sm:[&_td]:flex max-sm:[&_td]:min-w-0 max-sm:[&_td]:flex-wrap max-sm:[&_td]:items-center max-sm:[&_td]:justify-between max-sm:[&_td]:gap-x-3 max-sm:[&_td]:border-0 max-sm:[&_td]:p-0 max-sm:[&_td]:text-left',
  'max-sm:[&_td:first-child]:text-[16px] max-sm:[&_td:empty]:hidden',
].join(' ')

/**
 * Data tables as in Members, Targets, Supporters, Tally. Wraps in a horizontal scroller for phones;
 * `stack` instead turns each row into a card on phones, so nothing is wider than the screen.
 */
export function Table({ className, minWidth = 600, stack = false, style, ...props }: React.TableHTMLAttributes<HTMLTableElement> & { minWidth?: number; stack?: boolean }) {
  const ref = React.useRef<HTMLTableElement>(null)
  React.useLayoutEffect(() => {
    const table = ref.current
    if (!stack || !table) return
    const heads = [...table.querySelectorAll('thead th')].map((th) => th.textContent?.trim() || '')
    table.querySelectorAll('tbody tr').forEach((tr) => {
      ;[...tr.children].forEach((td, i) => {
        const label = i > 0 && !td.hasAttribute('colspan') ? heads[i] : ''
        if (label) td.setAttribute('data-label', label)
        else td.removeAttribute('data-label')
      })
    })
  })
  return (
    <div className={stack ? 'sm:overflow-x-auto' : 'overflow-x-auto'}>
      <table
        ref={ref}
        data-slot="table"
        style={{ ...style, ['--table-min' as string]: `${minWidth}px` }}
        className={cn('w-full border-collapse text-body', stack ? cn('sm:min-w-(--table-min)', STACK) : 'min-w-(--table-min)', className)}
        {...props}
      />
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
/** A column head; `srOnly` keeps its words for screen readers only, as over a column of buttons. */
export function TH({ className, align, srOnly, children, ...props }: React.ThHTMLAttributes<HTMLTableCellElement> & { srOnly?: boolean }) {
  return (
    <th scope="col" className={cn('px-3 py-2.5 text-left text-small font-semibold text-muted-foreground border-b border-line', align === 'right' && 'text-right', className)} {...props}>
      {srOnly ? <span className="sr-only">{children}</span> : children}
    </th>
  )
}
export function TD({ className, align, numeric, ...props }: React.TdHTMLAttributes<HTMLTableCellElement> & { numeric?: boolean }) {
  return <td className={cn('p-3 border-b border-line-soft max-sm:[&[data-label]]:before:content-[attr(data-label)] max-sm:[&[data-label]]:before:text-small max-sm:[&[data-label]]:before:font-semibold max-sm:[&[data-label]]:before:text-muted-foreground', (align === 'right' || numeric) && 'text-right', numeric && 'tabular-nums', className)} {...props} />
}
/** The one row a table shows when it has nothing to list; it spans every column. */
export function EmptyRow({ className, children }: { className?: string; children: React.ReactNode }) {
  return <TR><TD colSpan={99} className={cn('text-muted-foreground', className)}>{children}</TD></TR>
}
/** Row name that opens a detail panel: bold, underlined with a soft line */
export function RowButton({ className, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button type="button" className={cn('cursor-pointer bg-transparent py-1.5 text-left font-bold text-ink underline decoration-input underline-offset-[3px]', className)} {...props} />
}
