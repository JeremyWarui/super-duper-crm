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

type Figure = [label: string, value: React.ReactNode, note?: React.ReactNode, tone?: string]

/** The dark band of headline figures: label, figure in `tone` (e.g. "text-accent") and an optional note. */
export function FigureBand({ figures, label }: { figures: Figure[]; label: string }) {
  return (
    <section aria-label={label} className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-6 rounded-card bg-ink p-7 text-on-dark">
      {figures.map(([name, value, note, tone]) => (
        <div key={name} className="flex flex-col gap-1.5">
          <span className="text-ui font-semibold text-on-dark-muted">{name}</span>
          <span className={cn('font-display text-[36px] leading-none font-extrabold tabular-nums', tone)}>{value}</span>
          {note ? <span className="text-small text-on-dark-muted">{note}</span> : null}
        </div>
      ))}
    </section>
  )
}
