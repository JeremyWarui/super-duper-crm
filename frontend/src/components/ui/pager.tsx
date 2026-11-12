import { Button } from './button'

/** "51–100 of 240" with Previous and Next, for a list fetched `size` rows at a time from `offset`. */
export function Pager({ offset, size, shown, total, noun, onChange }: {
  offset: number
  size: number
  shown: number
  total: number
  noun: string
  onChange: (offset: number) => void
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <span className="text-ui text-muted-foreground">{total === 0 ? `0 ${noun}` : `${offset + 1}–${offset + shown} of ${total}`}</span>
      <div className="flex gap-2">
        <Button size="sm" variant="quiet" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - size))}>Previous</Button>
        <Button size="sm" variant="quiet" disabled={offset + size >= total} onClick={() => onChange(offset + size)}>Next</Button>
      </div>
    </div>
  )
}
