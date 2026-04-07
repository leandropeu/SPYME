export default function StatusBadge({ status }) {
  const normalized = (status || 'unknown').toLowerCase()
  const labelMap = {
    online: 'Online',
    offline: 'Offline',
    warning: 'Alerta',
    unknown: 'Indefinido',
  }

  return <span className={`status-badge ${normalized}`}>{labelMap[normalized] || status}</span>
}
