import * as React from 'react'
import { useParty } from '@/api/hooks'

/**
 * Party branding, from the singleton PartySettings record (GET /api/party/).
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

/** Maps GET /api/party/ onto the kit's branding; hover is the primary darkened, tint the primary over white. */
export function fromSettings(p: Record<string, any>): Branding {
  const primary = (p.primary_colour || defaultBranding.colors.primary).toUpperCase()
  return {
    partyName: p.name || defaultBranding.partyName,
    shortName: (p.short_name || p.name?.[0] || '').slice(0, 3),
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
}

const Ctx = React.createContext<Branding>(defaultBranding)
export const useBranding = () => React.useContext(Ctx)

export function BrandingProvider({ children }: { children: React.ReactNode }) {
  const party = useParty().data
  const b = React.useMemo(() => (party ? fromSettings(party) : defaultBranding), [party])
  React.useEffect(() => applyBranding(b), [b])
  React.useEffect(() => { if (party?.name) document.title = party.name }, [party?.name])
  return <Ctx.Provider value={b}>{children}</Ctx.Provider>
}
