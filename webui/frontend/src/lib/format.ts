export function formatProgress(progress: number): string {
  return `${Math.round(progress * 100)}%`
}

export function formatPercentage(n: number, decimals: number = 1): string {
  return `${(n * 100).toFixed(decimals)}%`
}

export function formatMm(mm: number): string {
  return `${mm.toFixed(2)}mm`
}

export function formatIteration(current: number, total: number): string {
  return `${Math.round(current)} / ${Math.round(total)}`
}

export function formatHex(hex: string): string {
  return hex.startsWith('#') ? hex.toLowerCase() : `#${hex.toLowerCase()}`
}
