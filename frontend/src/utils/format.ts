/**
 * Format a number as currency
 */
export function formatCurrency(value: number, decimals = 2): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value)
}

/**
 * Format a number with compact notation (K, M, B)
 */
export function formatCompact(value: number): string {
  if (Math.abs(value) >= 1e9) {
    return `${(value / 1e9).toFixed(2)}B`
  }
  if (Math.abs(value) >= 1e6) {
    return `${(value / 1e6).toFixed(2)}M`
  }
  if (Math.abs(value) >= 1e3) {
    return `${(value / 1e3).toFixed(2)}K`
  }
  return value.toFixed(2)
}

/**
 * Format a percentage
 */
export function formatPercent(value: number, decimals = 2): string {
  return `${(value * 100).toFixed(decimals)}%`
}

/**
 * Format a signed percentage (with + for positive)
 */
export function formatSignedPercent(value: number, decimals = 2): string {
  const formatted = (value * 100).toFixed(decimals)
  return value >= 0 ? `+${formatted}%` : `${formatted}%`
}

/**
 * Format price based on value magnitude
 */
export function formatPrice(value: number): string {
  if (value >= 10000) {
    return value.toFixed(0)
  }
  if (value >= 100) {
    return value.toFixed(2)
  }
  if (value >= 1) {
    return value.toFixed(4)
  }
  return value.toFixed(6)
}

/**
 * Format a timestamp (handles UTC timestamps from backend)
 */
export function formatTime(timestamp: string | Date): string {
  let date: Date
  if (typeof timestamp === 'string') {
    // If no timezone info, treat as UTC
    const utcTs = timestamp.endsWith('Z') || timestamp.includes('+') ? timestamp : timestamp + 'Z'
    date = new Date(utcTs)
  } else {
    date = timestamp
  }
  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
}

/**
 * Format a date (handles UTC timestamps from backend)
 */
export function formatDate(timestamp: string | Date): string {
  let date: Date
  if (typeof timestamp === 'string') {
    // If no timezone info, treat as UTC
    const utcTs = timestamp.endsWith('Z') || timestamp.includes('+') ? timestamp : timestamp + 'Z'
    date = new Date(utcTs)
  } else {
    date = timestamp
  }
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  })
}

/**
 * Format funding rate (usually in bps)
 */
export function formatFunding(value: number): string {
  const bps = value * 10000
  const sign = bps >= 0 ? '+' : ''
  return `${sign}${bps.toFixed(4)} bps`
}

/**
 * Get color class based on value
 */
export function getValueColor(value: number): string {
  if (value > 0) return 'text-bull'
  if (value < 0) return 'text-bear'
  return 'text-terminal-muted'
}

/**
 * Get background color class based on value
 */
export function getValueBgColor(value: number): string {
  if (value > 0) return 'bg-bull/10'
  if (value < 0) return 'bg-bear/10'
  return 'bg-terminal-border/50'
}

