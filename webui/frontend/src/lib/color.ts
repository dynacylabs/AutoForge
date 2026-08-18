export function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  if (!result) return null
  return {
    r: parseInt(result[1], 16),
    g: parseInt(result[2], 16),
    b: parseInt(result[3], 16),
  }
}

export function luminance(hex: string): number {
  const rgb = hexToRgb(hex)
  if (!rgb) return 0
  const srgb = [rgb.r, rgb.g, rgb.b].map((c) => {
    const s = c / 255
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4)
  })
  return 0.2126 * srgb[0] + 0.7152 * srgb[1] + 0.0722 * srgb[2]
}

export function contrastTextColor(hex: string): string {
  return luminance(hex) > 0.5 ? '#000000' : '#ffffff'
}

export function hexToTdOverlay(td: number, maxTd: number = 20): string {
  const alpha = Math.min(td / maxTd, 1)
  return `rgba(255, 255, 255, ${alpha * 0.5})`
}

export function lerpColor(a: string, b: string, t: number): string {
  const ar = hexToRgb(a)
  const br = hexToRgb(b)
  if (!ar || !br) return a
  const r1 = Math.round(ar.r + (br.r - ar.r) * t)
  const g1 = Math.round(ar.g + (br.g - ar.g) * t)
  const b1 = Math.round(ar.b + (br.b - ar.b) * t)
  return `#${((1 << 24) | (r1 << 16) | (g1 << 8) | b1).toString(16).slice(1)}`
}

export function normalizeHex(hex: string): string {
  return hex.startsWith('#') ? hex.toUpperCase() : `#${hex.toUpperCase()}`
}

export function luminanceContrast(a: string, b: string): number {
  const la = luminance(a)
  const lb = luminance(b)
  const lighter = Math.max(la, lb)
  const darker = Math.min(la, lb)
  return (lighter + 0.05) / (darker + 0.05)
}
