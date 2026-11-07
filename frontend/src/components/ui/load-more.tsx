import { Button } from './button'

/**
 * The line under a long list: "Showing 50 of 240 members" and a Load more button while more remain.
 * Leave `total` out when the server does not count; the line then reads "Showing 50 members".
 */
export function LoadMore({ shown, total, noun, hasMore, loading, onMore }: {
  shown: number
  total?: number
  noun: string
  hasMore: boolean
  loading?: boolean
  onMore: () => void
}) {
  if (shown === 0 && !hasMore) return null
  return (
    <div className="flex flex-col items-center gap-2 py-2">
      <p className="text-ui text-muted-foreground" aria-live="polite">
        {total === undefined ? `Showing ${shown} ${noun}` : `Showing ${shown} of ${total} ${noun}`}
      </p>
      {hasMore ? (
        <Button shape="rounded" variant="quiet" disabled={loading} onClick={onMore}>
          {loading ? 'Loading…' : 'Load more'}
        </Button>
      ) : null}
    </div>
  )
}
