import { LogOut, RefreshCcw, ShieldCheck } from 'lucide-react'

import { roleLabel } from '../utils/auth'

export default function Topbar({ title, subtitle, onRefresh, connected, currentUser, onLogout }) {
  return (
    <header className="topbar">
      <div>
        <div className="eyebrow">SPYGYM / Controle operacional</div>
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>

      <div className="topbar-actions">
        {currentUser ? (
          <div className="user-chip">
            <strong>{currentUser.full_name}</strong>
            <span>{roleLabel(currentUser.role)}</span>
          </div>
        ) : null}
        <div className={`connection-pill ${connected ? 'online' : 'offline'}`}>
          <ShieldCheck size={16} />
          <span>{connected ? 'Sincronizado' : 'Sem sincronização'}</span>
        </div>
        {onRefresh ? (
          <button type="button" className="button ghost" onClick={onRefresh}>
            <RefreshCcw size={16} />
            Atualizar
          </button>
        ) : null}
        {onLogout ? (
          <button type="button" className="button danger" onClick={onLogout}>
            <LogOut size={16} />
            Sair
          </button>
        ) : null}
      </div>
    </header>
  )
}
