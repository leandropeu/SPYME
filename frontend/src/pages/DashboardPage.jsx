import { useEffect, useState } from 'react'
import { Activity, AlertTriangle, Camera, HardDrive, MapPinned, ShieldCheck } from 'lucide-react'

import StatusBadge from '../components/StatusBadge'
import Topbar from '../components/Topbar'
import { api } from '../utils/api'
import { canManage } from '../utils/auth'
import { formatDate } from '../utils/format'

function StatCard({ icon: Icon, label, value, tone }) {
  return (
    <article className={`stat-card ${tone}`}>
      <div className="stat-icon">
        <Icon size={18} />
      </div>
      <div>
        <strong>{value}</strong>
        <span>{label}</span>
      </div>
    </article>
  )
}

export default function DashboardPage({ refreshToken, feed, connected, currentUser, onLogout }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const allowManage = canManage(currentUser)

  const load = async () => {
    try {
      setError('')
      setData(await api.getOverview())
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
        title="Centro de visão operacional"
        subtitle="Situação consolidada das unidades, DVRs, câmeras e backups."
        connected={connected}
        onRefresh={load}
        currentUser={currentUser}
        onLogout={onLogout}
      />

      {error ? <div className="alert-banner error">{error}</div> : null}

      <div className="stats-grid">
        <StatCard icon={MapPinned} label="Unidades" value={data?.totals.units ?? '—'} tone="blue" />
        <StatCard icon={HardDrive} label="DVRs online" value={data ? `${data.totals.online_dvrs}/${data.totals.dvrs}` : '—'} tone="green" />
        <StatCard icon={Camera} label="Câmeras online" value={data ? `${data.totals.online_cameras}/${data.totals.cameras}` : '—'} tone="amber" />
        <StatCard icon={AlertTriangle} label="Alertas críticos" value={data?.totals.critical_events ?? '—'} tone="red" />
      </div>

      <div className="panel-grid two-columns">
        <section className="panel">
          <div className="panel-header">
            <div>
              <span className="eyebrow">Malha das unidades</span>
              <h3>Vista rápida por academia</h3>
            </div>
          </div>
          <div className="unit-grid">
            {data?.units?.slice(0, 12).map((unit) => (
              <article key={unit.id} className="unit-card">
                <div className="unit-card-row">
                  <div>
                    <strong>{unit.name}</strong>
                    <span>{unit.city} / {unit.state}</span>
                  </div>
                  <StatusBadge status={unit.online_dvrs === unit.dvr_count ? 'online' : unit.online_dvrs > 0 ? 'warning' : 'offline'} />
                </div>
                <div className="metric-line">
                  <span>DVRs</span>
                  <strong>{unit.online_dvrs}/{unit.dvr_count}</strong>
                </div>
                <div className="metric-line">
                  <span>Câmeras</span>
                  <strong>{unit.online_cameras}/{unit.camera_count}</strong>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <span className="eyebrow">Incidentes abertos</span>
              <h3>Fila de atenção</h3>
            </div>
            {allowManage ? (
              <button type="button" className="button warning" onClick={() => api.runMonitor().then(load)}>
                <Activity size={16} />
                Rodar varredura
              </button>
            ) : null}
          </div>

          <div className="stack-list">
            {(data?.critical_events || []).map((event) => (
              <article key={event.id} className="event-item">
                <div className="event-item-head">
                  <strong>{event.title}</strong>
                  <StatusBadge status={event.severity === 'critical' ? 'offline' : 'warning'} />
                </div>
                <p>{event.message}</p>
                <span>{formatDate(event.started_at)}</span>
              </article>
            ))}
            {!data?.critical_events?.length ? <div className="empty-state">Nenhum incidente aberto no momento.</div> : null}
          </div>
        </section>
      </div>

      <div className="panel-grid two-columns">
        <section className="panel">
          <div className="panel-header">
            <div>
              <span className="eyebrow">Backups recentes</span>
              <h3>Proteção do banco SQLite</h3>
            </div>
          </div>
          <div className="stack-list">
            {(data?.latest_backups || []).map((backup) => (
              <article key={backup.id} className="backup-line">
                <div>
                  <strong>{backup.file_name}</strong>
                  <span>{formatDate(backup.started_at)}</span>
                </div>
                <StatusBadge status={backup.status === 'completed' ? 'online' : backup.status === 'failed' ? 'offline' : 'warning'} />
              </article>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <span className="eyebrow">Tempo real</span>
              <h3>Feed de atividade</h3>
            </div>
            <div className={`connection-pill ${connected ? 'online' : 'offline'}`}>
              <ShieldCheck size={16} />
              <span>{connected ? 'Feed ativo' : 'Feed indisponível'}</span>
            </div>
          </div>
          <div className="stack-list">
            {feed.map((item, index) => (
              <article key={`${item.type}-${index}`} className="feed-line">
                <strong>{item.title || item.type}</strong>
                <span>{item.checked_at ? formatDate(item.checked_at) : 'evento websocket'}</span>
              </article>
            ))}
            {!feed.length ? <div className="empty-state">Aguardando eventos em tempo real.</div> : null}
          </div>
        </section>
      </div>
    </section>
  )
}
