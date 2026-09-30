import type { ReactNode } from 'react'

interface PageHeaderProps {
  eyebrow?: string
  title: string
  description?: ReactNode
  actions?: ReactNode
  className?: string
}

export function PageHeader({ eyebrow, title, description, actions, className = '' }: PageHeaderProps) {
  return (
    <header className={`screen__head page-header ${className}`.trim()}>
      <div>
        {eyebrow && <p className='eyebrow'>{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p className='lede'>{description}</p>}
      </div>
      {actions && <div className='page-header__actions'>{actions}</div>}
    </header>
  )
}
