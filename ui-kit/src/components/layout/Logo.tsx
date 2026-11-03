import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { useBranding } from '@/theme/branding'

/** Logo tile + party name. size "lg" = website header (44px), "md" = footer/CRM (40px / 34px) */
export function Logo({ size = 'lg', onDark, withSlogan, to = '/' }: { size?: 'lg' | 'md' | 'sm'; onDark?: boolean; withSlogan?: boolean; to?: string }) {
  const b = useBranding()
  const tile = size === 'lg' ? 'size-11 rounded-lg text-[22px]' : size === 'md' ? 'size-10 rounded-[11px] text-[20px]' : 'size-[34px] rounded-[9px] text-[17px]'
  return (
    <Link to={to} className={cn('flex items-center gap-2.5 no-underline', onDark ? 'text-on-dark hover:text-on-dark' : 'text-ink hover:text-ink')}>
      {b.logoUrl ? (
        <img src={b.logoUrl} alt="" className={cn(tile, 'object-cover')} />
      ) : (
        <span aria-hidden className={cn(tile, 'flex items-center justify-center font-display font-extrabold', size === 'sm' ? 'bg-accent text-ink' : 'bg-primary text-accent')}>{b.shortName}</span>
      )}
      <span className="flex flex-col leading-[1.1]">
        <span className={cn('font-display font-extrabold', size === 'sm' ? 'text-lead' : 'text-[22px]')}>{b.partyName}</span>
        {withSlogan ? <span className="text-meta font-semibold text-muted-foreground">{b.slogan}</span> : null}
      </span>
    </Link>
  )
}
