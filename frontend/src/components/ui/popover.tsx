import * as React from 'react'
import * as PopoverPrimitive from '@radix-ui/react-popover'
import * as Menu from '@radix-ui/react-dropdown-menu'
import { cn } from '@/lib/utils'

export const Popover = PopoverPrimitive.Root
export const PopoverTrigger = PopoverPrimitive.Trigger
export function PopoverContent({ className, align = 'end', sideOffset = 8, ...props }: React.ComponentProps<typeof PopoverPrimitive.Content>) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content align={align} sideOffset={sideOffset} className={cn('z-50 w-[380px] max-w-[calc(100vw-32px)] rounded-[18px] border border-black/5 bg-popover p-2 shadow-pop outline-none', className)} {...props} />
    </PopoverPrimitive.Portal>
  )
}

export const DropdownMenu = Menu.Root
export const DropdownMenuTrigger = Menu.Trigger
export function DropdownMenuContent({ className, align = 'end', sideOffset = 8, ...props }: React.ComponentProps<typeof Menu.Content>) {
  return (
    <Menu.Portal>
      <Menu.Content align={align} sideOffset={sideOffset} className={cn('z-50 min-w-56 rounded-[18px] border border-black/5 bg-popover p-2 shadow-pop', className)} {...props} />
    </Menu.Portal>
  )
}
export function DropdownMenuItem({ className, ...props }: React.ComponentProps<typeof Menu.Item>) {
  return <Menu.Item className={cn('flex min-h-11 cursor-pointer items-center gap-2 rounded-md px-3 text-ui font-semibold text-ink outline-none data-[highlighted]:bg-stone', className)} {...props} />
}
export function DropdownMenuLabel({ className, ...props }: React.ComponentProps<typeof Menu.Label>) {
  return <Menu.Label className={cn('px-3 py-2 text-small text-muted-foreground', className)} {...props} />
}
export function DropdownMenuSeparator({ className, ...props }: React.ComponentProps<typeof Menu.Separator>) {
  return <Menu.Separator className={cn('my-1 h-px bg-line-soft', className)} {...props} />
}
