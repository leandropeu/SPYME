import { useEffect, useState } from 'react'

import StatusBadge from '../components/StatusBadge'
import Topbar from '../components/Topbar'
import { api } from '../utils/api'
import { formatDate } from '../utils/format'

export default function EventsPage({ refreshToken, connected, currentUser, onLogout }) {
  const [events, setEvents] = useState([])
  const [error, setError] = useState('')

  const load = async () => {
    try {
      setError('')
      setEvents(await api.listEvents(150))
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    load()
  }, [refreshToken])

  return (
    <section className="page-shell">
      <Topbar
        title="Linha de eventos"
        subtitle="Histórico de indisponibilidades, alertas e recuperações do ambiente."
        connected={connected}
        onRefresh={load}
        currentUser={currentUser}
        onLogout={onLogout}
      />

      {error ? <div className="alert-banner error">{error}</div> : null}

      <div className="timeline-list">
        {events.map((event) => (
          <article key={event.id} className="timeline-item">
            <div className={`timeline-mark ${event.severity}`} />
            <div className="timeline-content">
              <div className="timeline-head">
                <strong>{event.title}</strong>
                <StatusBadge status={event.severity === 'critical' ? 'offline' : event.severity === 'info' ? 'online' : 'warning'} />
              </div>
              <p>{event.message}</p>
              <span>{formatDate(event.started_at)}</span>
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}
