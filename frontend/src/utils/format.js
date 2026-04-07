function parseApiDate(value) {
  if (!value) return null
  if (value instanceof Date) return value

  if (typeof value === 'string') {
    const normalized = value.trim()
    // O backend hoje envia diversos timestamps em UTC sem o sufixo "Z".
    // Quando isso acontece, o navegador interpreta como horário local e o relógio fica adiantado.
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(normalized)) {
      return new Date(`${normalized}Z`)
    }
    return new Date(normalized)
  }

  return new Date(value)
}

export function formatDate(value) {
  const parsed = parseApiDate(value)
  if (!parsed || Number.isNaN(parsed.getTime())) return '—'

  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(parsed)
}

export function formatFileSize(value) {
  if (!value && value !== 0) return '—'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = value
  let unit = 0
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024
    unit += 1
  }
  return `${size.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`
}
