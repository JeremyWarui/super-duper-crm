/** The muted "Loading…" line a page or panel shows while its data arrives. */
export function LoadingText({ children = 'Loading…' }: { children?: string }) {
  return <p className="text-muted-foreground">{children}</p>
}
