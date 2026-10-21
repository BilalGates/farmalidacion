interface Props {
  readonly value: string
}

export function SourceValue({ value }: Props) {
  const trimmed = value.trim()
  let href: string | null = null
  try {
    const url = new URL(trimmed)
    if ((url.protocol === 'https:' || url.protocol === 'http:') && url.hostname) href = url.href
  } catch {
    // Los demás literales siguen mostrándose tal como llegaron del maestro.
  }
  return href
    ? <a href={href} target='_blank' rel='noopener noreferrer'>{value}</a>
    : <>{value}</>
}
