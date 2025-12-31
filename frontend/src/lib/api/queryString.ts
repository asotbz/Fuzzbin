export function toQueryString(params: Record<string, unknown>): string {
  const search = new URLSearchParams()

  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue

    if (typeof value === 'string') {
      const trimmed = value.trim()
      if (trimmed.length === 0) continue
      search.set(key, trimmed)
      continue
    }

    if (typeof value === 'number') {
      if (!Number.isFinite(value)) continue
      search.set(key, String(value))
      continue
    }

    if (typeof value === 'boolean') {
      search.set(key, value ? 'true' : 'false')
      continue
    }

    search.set(key, String(value))
  }

  const qs = search.toString()
  return qs.length > 0 ? `?${qs}` : ''
}
