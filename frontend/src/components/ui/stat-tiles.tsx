import * as React from 'react'
import { cn } from '@/lib/utils'
import { Card } from './card'

const COLUMNS = {
  150: 'grid-cols-[repeat(auto-fit,minmax(150px,1fr))]',
  200: 'grid-cols-[repeat(auto-fit,minmax(200px,1fr))]',
}

type Tile = [label: string, value: React.ReactNode, note?: React.ReactNode]

/** The "Summary" row of label, figure and optional note tiles, wrapping to fit; `min` is a tile's narrowest width in px. */
export function StatTiles({ tiles, min = 200, valueClassName }: { tiles: Tile[]; min?: keyof typeof COLUMNS; valueClassName?: string }) {
  return (
    <section aria-label="Summary" className={cn('grid gap-4', COLUMNS[min])}>
      {tiles.map(([label, value, ...note]) => (
        <Card key={label} variant="tile">
          <span className="text-ui text-muted-foreground">{label}</span>
          <span className={cn('font-display text-[28px] leading-tight font-extrabold tabular-nums', valueClassName)}>{value}</span>
          {note.length ? <span className="text-small text-muted-foreground">{note[0]}</span> : null}
        </Card>
      ))}
    </section>
  )
}
