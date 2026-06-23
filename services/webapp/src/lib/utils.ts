export function cn(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(' ')
}

export function formatNumber(value: number | null | undefined) {
  return new Intl.NumberFormat().format(value ?? 0)
}

export function formatPercent(value: number | null | undefined) {
  return `${(value ?? 0).toFixed(2)}%`
}

export function formatBytes(value: number | null | undefined) {
  const size = value ?? 0
  if (size < 1024) return `${size} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let unitIndex = -1
  let current = size
  do {
    current /= 1024
    unitIndex += 1
  } while (current >= 1024 && unitIndex < units.length - 1)
  return `${current.toFixed(current >= 10 ? 1 : 2)} ${units[unitIndex]}`
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}
