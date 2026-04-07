import { useEffect, useState } from 'react'
import { DatabaseBackup, Shield } from 'lucide-react'

import StatusBadge from '../components/StatusBadge'
import Topbar from '../components/Topbar'
import { api } from '../utils/api'
import { canManage } from '../utils/auth'
import { formatDate, formatFileSize } from '../utils/format'

export default function BackupsPage({ refreshToken, connected, currentUser, onLogout }) {
  const [backups, setBackups] = useState([])
  const [health, setHealth] = useState(null)
  const [error, setError] = useState('')
  const allowManage = canManage(currentUser)

  const load = async () => {
    try {
      setError('')
      const [backupData, healthData] = await Promise.all([api.listBackups(), api.health()])
      setBackups(backupData)
      setHealth(healthData)
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
        title="Backups automatizados"
        subtitle="Execução a cada duas horas, retenção de cinco dias e rotação controlada."
        connected={connected}
        onRefresh={load}
        currentUser={currentUser}
        onLogout={onLogout}
      />

      {error ? <div className="alert-banner error">{error}</div> : null}

      <div className="panel-grid two-columns">
        <section className="panel">
          <div className="panel-header">
            <div>
              <span className="eyebrow">Política ativa</span>
              <h3>Proteção do banco</h3>
            </div>
            {allowManage ? (
              <button type="button" className="button primary" onClick={() => api.runBackup().then(load)}>
                <DatabaseBackup size={16} />
                Fazer backup agora
              </button>
            ) : null}
          </div>
          <div className="stack-list">
            <article className="info-block">
              <Shield size={18} />
              <div>
                <strong>Intervalo</strong>
                <span>{health?.backup_interval_hours || 2} horas</span>
              </div>
            </article>
            <article className="info-block">
              <Shield size={18} />
              <div>
                <strong>Retenção</strong>
                <span>{health?.backup_retention_days || 5} dias</span>
              </div>
            </article>
            <article className="info-block">
              <Shield size={18} />
              <div>
                <strong>Pasta</strong>
                <span>{health?.backup_dir || '—'}</span>
              </div>
            </article>
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <span className="eyebrow">Histórico</span>
              <h3>Últimos arquivos gerados</h3>
            </div>
          </div>
          <div className="stack-list">
            {backups.map((backup) => (
              <article key={backup.id} className="backup-line">
                <div>
                  <strong>{backup.file_name}</strong>
                  <span>{formatDate(backup.started_at)} • {formatFileSize(backup.file_size)}</span>
                </div>
                <StatusBadge status={backup.status === 'completed' ? 'online' : backup.status === 'failed' ? 'offline' : 'warning'} />
              </article>
            ))}
            {!backups.length ? <div className="empty-state">Nenhum backup executado ainda.</div> : null}
          </div>
        </section>
      </div>
    </section>
  )
}
