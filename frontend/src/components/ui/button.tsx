import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

/**
 * Buttons as drawn in the mockups.
 * - Website buttons are pills (shape="pill", the default).
 * - CRM / workspace buttons have 12px corners (shape="rounded").
 * Minimum height is 44px everywhere (touch target).
 */
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap font-bold no-underline transition-colors cursor-pointer select-none disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        primary: 'bg-primary text-primary-foreground hover:bg-primary-hover hover:text-primary-foreground',
        accent: 'bg-accent text-accent-foreground hover:brightness-95 hover:text-accent-foreground',
        ink: 'bg-ink text-white hover:bg-ink-2 hover:text-white',
        outline: 'bg-white text-ink border-[1.5px] border-ink hover:bg-stone hover:text-ink',
        quiet: 'bg-white text-ink border border-line-control hover:bg-stone hover:text-ink',
        onDark: 'bg-transparent text-white border-[1.5px] border-white hover:bg-white/10 hover:text-white',
        ghost: 'bg-transparent text-ink hover:bg-stone hover:text-ink',
        danger: 'bg-white text-bad-foreground border border-[#E8C4C0] hover:bg-bad hover:text-bad-foreground',
        link: 'bg-transparent text-primary underline-offset-4 hover:underline h-auto px-0',
      },
      size: {
        sm: 'h-10 px-4 text-ui max-sm:h-11',
        md: 'h-11 px-5 text-body',
        lg: 'h-[52px] px-7 text-[17px]',
        icon: 'h-11 w-11 p-0',
      },
      shape: {
        pill: 'rounded-full',
        rounded: 'rounded-lg',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md', shape: 'pill' },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

export function Button({ className, variant, size, shape, asChild = false, type, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : 'button'
  return (
    <Comp
      data-slot="button"
      type={asChild ? undefined : (type ?? 'button')}
      className={cn(buttonVariants({ variant, size, shape }), className)}
      {...props}
    />
  )
}
