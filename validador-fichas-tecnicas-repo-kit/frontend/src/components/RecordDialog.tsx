import { useEffect, useRef, type ReactNode } from 'react'

export function RecordDialog({ open, onClose, children, titleId = 'record-dialog-title' }: { open: boolean; onClose: () => void; children: ReactNode; titleId?: string }) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const dialog = ref.current
    if (!open || !dialog) return
    const previous = document.activeElement as HTMLElement | null
    const overflow = document.body.style.overflow
    dialog.showModal()
    document.body.style.overflow = 'hidden'
    return () => {
      dialog.close()
      document.body.style.overflow = overflow
      if (previous?.isConnected) previous.focus({ preventScroll: true })
    }
  }, [open])
  return <dialog ref={ref} className='record-dialog' aria-labelledby={titleId} onCancel={event => { event.preventDefault(); onClose() }}>
    {children}
  </dialog>
}
