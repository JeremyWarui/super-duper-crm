import * as React from 'react'
import { useParty, useSite } from '@/api/hooks'

/**
 * Site branding, from the site settings (GET /api/site/); the registration number is party-only.
 * Only colours, names and images change per party. Spacing, type, radii and
 * neutrals are fixed by the platform so every party copy stays on-design.
 */
export type Branding = {
  partyName: string
  shortName: string            // logo tile letter(s), e.g. "P"
  slogan: string
  registrationNo: string
  hotline: string
  logoUrl?: string | null
  colors: {
    primary: string            // buttons, active nav, links
    primaryHover: string
    primaryTint: string        // light tint of primary for pills / icon tiles
    accent: string             // gold-style highlight; text on it is ink
  }
}

export const defaultBranding: Branding = {
  partyName: '',
  shortName: '',
  slogan: '',
  registrationNo: '',
  hotline: '',
  logoUrl: null,
  colors: { primary: '#0B5D3B', primaryHover: '#08442B', primaryTint: '#E7F0EA', accent: '#F2B705' },
}

const shade = (hex: string, f: (c: number) => number) =>
  '#' + [1, 3, 5].map((i) => Math.round(f(parseInt(hex.slice(i, i + 2), 16))).toString(16).padStart(2, '0')).join('').toUpperCase()

/** The logo tile's letters: a short name of up to three characters, else up to two initials of the name. */
const tileMark = (short?: string, name?: string) => {
  const s = (short || '').trim()
  if (s && Array.from(s).length <= 3) return s
  return (name || s).split(/\s+/).filter(Boolean).slice(0, 2).map((w) => Array.from(Array.from(w)[0].toLocaleUpperCase())[0]).join('')
}

/** Maps GET /api/site/ (plus the party's registration number) onto the kit's branding; hover is the primary darkened, tint the primary over white. */
export function fromSettings(p: Record<string, any>): Branding {
  const primary = (p.primary_colour || defaultBranding.colors.primary).toUpperCase()
  return {
    partyName: p.name || defaultBranding.partyName,
    shortName: tileMark(p.short_name, p.name),
    slogan: p.slogan ?? '',
    registrationNo: p.registration_number ?? '',
    hotline: p.contact_phone ?? '',
    logoUrl: p.logo_url || null,
    colors: {
      primary,
      primaryHover: shade(primary, (c) => c * 0.73),
      primaryTint: shade(primary, (c) => c * 0.1 + 255 * 0.9),
      accent: (p.secondary_colour || defaultBranding.colors.accent).toUpperCase(),
    },
  }
}

export function applyBranding(b: Branding) {
  const r = document.documentElement.style
  r.setProperty('--party-primary', b.colors.primary)
  r.setProperty('--party-primary-hover', b.colors.primaryHover)
  r.setProperty('--party-primary-tint', b.colors.primaryTint)
  r.setProperty('--party-accent', b.colors.accent)
  let icon = document.querySelector<HTMLLinkElement>('link[rel=icon]')
  if (!icon) {
    icon = document.createElement('link')
    icon.rel = 'icon'
    document.head.appendChild(icon)
  }
  icon.href = b.logoUrl || tileIcon(b)
}

/** The logo tile as an SVG data URI, for the tab icon when there is no logo. */
const tileIcon = (b: Branding) => {
  const letters = b.shortName.replace(/[<>&"']/g, '')
  const size = letters.length > 2 ? 26 : 36
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="${b.colors.primary}"/><text x="32" y="33" font-family="system-ui,sans-serif" font-size="${size}" font-weight="800" fill="${b.colors.accent}" text-anchor="middle" dominant-baseline="central">${letters}</text></svg>`
  return `data:image/svg+xml,${encodeURIComponent(svg)}`
}

const Ctx = React.createContext<Branding>(defaultBranding)
export const useBranding = () => React.useContext(Ctx)

export function BrandingProvider({ children }: { children: React.ReactNode }) {
  const site = useSite().data
  const party = useParty(site?.organisation_type === 'party').data
  const b = React.useMemo(
    () => (site ? fromSettings({ ...site, registration_number: party?.registration_number }) : defaultBranding),
    [site, party?.registration_number],
  )
  React.useEffect(() => applyBranding(b), [b])
  React.useEffect(() => { if (site?.name) document.title = site.name }, [site?.name])
  return <Ctx.Provider value={b}>{children}</Ctx.Provider>
}
