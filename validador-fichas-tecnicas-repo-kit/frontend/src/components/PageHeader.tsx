import type { ReactNode } from 'react'

interface PageHeaderProps {
  eyebrow?: string
  title: string
  description?: ReactNode
  actions?: ReactNode
  className?: string
  headingLevel?: 1 | 2
}

export function PageHeader({ eyebrow, title, description, actions, className = '', headingLevel = 1 }: PageHeaderProps) {
  const Heading = headingLevel === 2 ? 'h2' : 'h1'
  return (
    <header className={`screen__head page-header ${className}`.trim()}>
      <div>
        {eyebrow && <p className='eyebrow'>{eyebrow}</p>}
        <Heading>{title}</Heading>
        {description && <p className='lede'>{description}</p>}
      </div>
      {actions && <div className='page-header__actions'>{actions}</div>}
    </header>
  )
}
