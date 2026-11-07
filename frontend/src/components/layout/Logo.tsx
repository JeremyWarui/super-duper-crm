import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { useBranding } from '@/theme/branding'

/**
 * Logo tile + party name. size "lg" = website header (44px), "md" = footer/CRM (40px / 34px).
 * onPrimary is for a party-green panel: a gold tile and light text.
 */
export function Logo({ size = 'lg', onDark, onPrimary, withSlogan, to = '/' }: { size?: 'lg' | 'md' | 'sm'; onDark?: boolean; onPrimary?: boolean; withSlogan?: boolean; to?: string }) {
  const b = useBranding()
  const three = b.shortName.length > 2
  const tile = size === 'lg'
    ? cn('size-11 rounded-lg', three ? 'text-[15px]' : 'text-[22px]')
    : size === 'md'
      ? cn('size-10 rounded-[11px]', three ? 'text-[14px]' : 'text-[20px]')
      : cn('size-[34px] rounded-[9px]', three ? 'text-[12px]' : 'text-[17px]')
  return (
    <Link to={to} className={cn('flex items-center gap-2.5 no-underline', onDark || onPrimary ? 'text-on-dark hover:text-on-dark' : 'text-ink hover:text-ink')}>
      {b.logoUrl ? (
        <img src={b.logoUrl} alt="" className={cn(tile, 'flex-none object-cover')} />
      ) : (
        <span aria-hidden className={cn(tile, 'flex flex-none items-center justify-center font-display font-extrabold', size === 'sm' || onPrimary ? 'bg-accent text-ink' : 'bg-primary text-accent')}>{b.shortName}</span>
      )}
      <span className="flex flex-col leading-[1.1]">
        <span className={cn('font-display font-extrabold', size === 'sm' ? 'text-lead' : 'text-[22px]')}>{b.partyName}</span>
        {withSlogan ? <span className="text-meta font-semibold text-muted-foreground">{b.slogan}</span> : null}
      </span>
    </Link>
  )
}
