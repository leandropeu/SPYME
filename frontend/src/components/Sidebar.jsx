import { Activity, Camera, DatabaseBackup, HardDrive, MapPinned, ShieldAlert } from 'lucide-react'

import { roleLabel } from '../utils/auth'

const items = [
  { id: 'units', label: 'Unidades', icon: MapPinned },
  { id: 'dvrs', label: 'DVRs', icon: HardDrive },
  { id: 'cameras', label: 'Cameras', icon: Camera },
  { id: 'events', label: 'Eventos', icon: ShieldAlert },
  { id: 'backups', label: 'Backups', icon: DatabaseBackup },
]

export default function Sidebar({ page, setPage, connected, currentUser }) {
  return (
    <aside className="sidebar">
      <div className="brand-panel">
        <div className="brand-chip">SPYGYM</div>
        <h1>Gestao de DVRs e cameras</h1>
        <p>Operacao remota de gravadores, visualizacao, reproducoes, eventos e backups por unidade.</p>
      </div>

      <nav className="sidebar-nav">
        {items.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            className={`nav-item ${page === id ? 'active' : ''}`}
            onClick={() => setPage(id)}
          >
            <Icon size={18} />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      <div className="user-panel">
        <strong>{currentUser?.full_name}</strong>
        <span>{currentUser?.email}</span>
        <span className="user-role">{roleLabel(currentUser?.role)}</span>
      </div>

      <div className="sidebar-status">
        <div className={`status-led ${connected ? 'online' : 'offline'}`} />
        <div>
          <strong>Canal em tempo real</strong>
          <span>{connected ? 'WebSocket conectado' : 'Reconectando...'}</span>
        </div>
        <Activity size={18} />
      </div>
    </aside>
  )
}
