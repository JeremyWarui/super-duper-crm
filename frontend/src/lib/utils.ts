import { clsx, type ClassValue } from 'clsx'
import { extendTailwindMerge } from 'tailwind-merge'

/**
 * tailwind-merge must know our custom type scale, otherwise it treats
 * `text-meta` as a colour and silently drops it when combined with
 * `text-muted-foreground`. Keep this list in sync with --text-* in globals.css.
 */
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      'font-size': [{ text: ['meta', 'small', 'ui', 'body', 'base', 'lead', 'card-title', 'h3', 'h2-app', 'section', 'page', 'hero'] }],
      shadow: [{ shadow: ['card', 'pop', 'hero-card'] }],
      rounded: [{ rounded: ['photo', 'card', 'panel', 'band'] }],
    },
  },
})

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
