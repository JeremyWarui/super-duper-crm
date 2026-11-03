import * as React from 'react'

/**
 * Party branding. FastAPI returns this from GET /api/branding, read from the
 * singleton PartySettings record (one installation = one party).
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
  partyName: 'Pamoja Party',
  shortName: 'P',
  slogan: '[Party slogan]',
  registrationNo: '[000]',
  hotline: '[0700 000 000]',
  logoUrl: null,
  colors: { primary: '#0B5D3B', primaryHover: '#08442B', primaryTint: '#E7F0EA', accent: '#F2B705' },
}

export function applyBranding(b: Branding) {
  const r = document.documentElement.style
  r.setProperty('--party-primary', b.colors.primary)
  r.setProperty('--party-primary-hover', b.colors.primaryHover)
  r.setProperty('--party-primary-tint', b.colors.primaryTint)
  r.setProperty('--party-accent', b.colors.accent)
  document.title = b.partyName
}

const Ctx = React.createContext<Branding>(defaultBranding)
export const useBranding = () => React.useContext(Ctx)

export function BrandingProvider({ children }: { children: React.ReactNode }) {
  const [b, setB] = React.useState<Branding>(defaultBranding)
  React.useEffect(() => {
    let alive = true
    fetch('/api/branding')
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data: Branding) => { if (alive) { setB(data); applyBranding(data) } })
      .catch(() => applyBranding(defaultBranding)) // offline / dev without API: keep defaults
    return () => { alive = false }
  }, [])
  return <Ctx.Provider value={b}>{children}</Ctx.Provider>
}
