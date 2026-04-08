import { Activity, Camera, Cloud, DatabaseBackup, FileText, HardDrive, LayoutDashboard, MapPinned, Network, ShieldAlert, Users } from 'lucide-react'

import { isAdmin, roleLabel } from '../utils/auth'

const items = [
  { id: 'dashboard', label: 'Painel', icon: LayoutDashboard },
  { id: 'units', label: 'Unidades', icon: MapPinned },
  { id: 'mikrotik', label: 'MikroTik', icon: Network },
  { id: 'dvrs', label: 'DVRs', icon: HardDrive },
  { id: 'cloud-accounts', label: 'Contas cloud', icon: Cloud },
  { id: 'network-assets', label: 'Ativos de rede', icon: Network },
  { id: 'cameras', label: 'Cameras', icon: Camera },
  { id: 'reports', label: 'Relatorios', icon: FileText },
  { id: 'events', label: 'Eventos', icon: ShieldAlert },
  { id: 'backups', label: 'Backups', icon: DatabaseBackup },
]

export default function Sidebar({ page, setPage, connected, currentUser }) {
  const navItems = isAdmin(currentUser)
    ? [...items, { id: 'users', label: 'Usuarios', icon: Users }]
    : items

  return (
    <aside className="sidebar">
      <div className="brand-panel">
        <div className="brand-chip">SPYGYM</div>
        <h1>Monitoramento em tempo real</h1>
        <p>DVRs, rede, eventos e acessos tecnicos em um unico painel operacional.</p>
      </div>

      <nav className="sidebar-nav">
        {navItems.map(({ id, label, icon: Icon }) => (
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
