import * as React from 'react'

const canAnimate = () =>
  typeof window !== 'undefined' &&
  typeof window.IntersectionObserver === 'function' &&
  !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/**
 * Slides its children up into view the first time they scroll on screen; a `.reveal-stagger` grid inside
 * brings its items in one after another.
 * Shows at once when the browser cannot watch scrolling or the visitor asks for less motion.
 */
export function Reveal({ children, className }: { children: React.ReactNode; className?: string }) {
  const ref = React.useRef<HTMLDivElement>(null)
  const [shown, setShown] = React.useState(() => !canAnimate())
  React.useEffect(() => {
    if (shown || !ref.current) return
    const watch = new IntersectionObserver(
      (entries) => {
        // A section already scrolled past, as after a jump to an anchor lower down, shows without waiting.
        if (entries.some((e) => e.isIntersecting || e.boundingClientRect.bottom < 0)) {
          setShown(true)
          watch.disconnect()
        }
      },
      { rootMargin: '0px 0px -12% 0px' },
    )
    watch.observe(ref.current)
    return () => watch.disconnect()
  }, [shown])
  return <div ref={ref} data-reveal={shown ? 'in' : 'out'} className={className}>{children}</div>
}
