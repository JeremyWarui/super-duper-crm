import * as React from 'react'
import { linkNote } from '@/lib/invite'
import { Button } from './button'
import { Dialog } from './dialog'
import { FormActions } from './form-actions'

/** Shown after a login is made: whether its invite went out by email, then anything the caller adds. */
export function InviteDialog({ title, invite, username, onClose, children }: {
  title: React.ReactNode
  invite: string
  username: string
  onClose: () => void
  children?: React.ReactNode
}) {
  return (
    <Dialog title={title} description={linkNote(invite, username)} onClose={onClose}>
      {children ? <div className="flex flex-col gap-2 text-ui">{children}</div> : null}
      <FormActions><Button onClick={onClose}>Done</Button></FormActions>
    </Dialog>
  )
}
