import { useEffect, useMemo, useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'

import EntityModal from '../components/EntityModal'
import StatusBadge from '../components/StatusBadge'
import Topbar from '../components/Topbar'
import ViewToggle from '../components/ViewToggle'
import { api } from '../utils/api'
import { roleLabel } from '../utils/auth'
import { formatDate } from '../utils/format'

export default function UsersPage({ refreshToken, connected, currentUser, onLogout }) {
  const [users, setUsers] = useState([])
  const [view, setView] = useState('list')
  const [search, setSearch] = useState('')
  const [editing, setEditing] = useState(null)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')

  const fields = [
    { name: 'full_name', label: 'Nome completo' },
    { name: 'email', label: 'E-mail' },
    { name: 'role', label: 'Perfil', type: 'select', options: [
      { value: 'admin', label: 'Administrador' },
      { value: 'operator', label: 'Operador' },
      { value: 'viewer', label: 'Visualizador' },
    ] },
    { name: 'is_active', label: 'Ativo', type: 'select', options: [
      { value: 'true', label: 'Sim' },
      { value: 'false', label: 'Não' },
    ] },
    { name: 'password', label: 'Senha', type: 'password', full: true },
  ]

  const load = async () => {
    try {
      setError('')
      setUsers(await api.listUsers())
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    load()
  }, [refreshToken])

  const filtered = useMemo(
    () => users.filter((user) => `${user.full_name} ${user.email} ${user.role}`.toLowerCase().includes(search.toLowerCase())),
    [users, search],
  )

  const save = async (form) => {
    const payload = {
      ...form,
      is_active: String(form.is_active) !== 'false',
    }
    if (!payload.password) {
      delete payload.password
    }

    if (editing?.id) {
      await api.updateUser(editing.id, payload)
    } else {
      await api.createUser(payload)
    }
    setOpen(false)
    setEditing(null)
    load()
  }

  return (
    <section className="page-shell">
      <Topbar
        title="Usuários e perfis"
        subtitle="Controle de acesso por administrador, operador e visualizador."
        connected={connected}
        onRefresh={load}
        currentUser={currentUser}
        onLogout={onLogout}
      />

      <div className="toolbar">
        <input className="search-input" placeholder="Buscar por nome, e-mail ou perfil" value={search} onChange={(event) => setSearch(event.target.value)} />
        <ViewToggle mode={view} setMode={setView} />
        <button type="button" className="button primary" onClick={() => { setEditing(null); setOpen(true) }}>
          <Plus size={16} />
          Novo usuário
        </button>
      </div>

      {error ? <div className="alert-banner error">{error}</div> : null}

      {view === 'cards' ? (
        <div className="card-grid">
          {filtered.map((user) => (
            <article key={user.id} className="entity-card">
              <div className="entity-card-header">
                <div>
                  <strong>{user.full_name}</strong>
                  <span>{user.email}</span>
                </div>
                <StatusBadge status={user.is_active ? 'online' : 'offline'} />
              </div>
              <div className="entity-card-body">
                <div className="metric-line"><span>Perfil</span><strong>{roleLabel(user.role)}</strong></div>
                <div className="metric-line"><span>Último login</span><strong>{formatDate(user.last_login_at)}</strong></div>
              </div>
              <div className="entity-card-actions">
                <button type="button" className="button ghost" onClick={() => { setEditing({ ...user, is_active: String(user.is_active) }); setOpen(true) }}>
                  <Pencil size={16} />
                  Editar
                </button>
                <button type="button" className="button danger" onClick={() => window.confirm(`Excluir ${user.full_name}?`) && api.deleteUser(user.id).then(load)}>
                  <Trash2 size={16} />
                  Excluir
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="table-shell">
          <table>
            <thead>
              <tr>
                <th>Usuário</th>
                <th>Perfil</th>
                <th>Status</th>
                <th>Último login</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filtered.map((user) => (
                <tr key={user.id}>
                  <td>
                    <strong>{user.full_name}</strong>
                    <span>{user.email}</span>
                  </td>
                  <td>{roleLabel(user.role)}</td>
                  <td><StatusBadge status={user.is_active ? 'online' : 'offline'} /></td>
                  <td>{formatDate(user.last_login_at)}</td>
                  <td className="actions-cell">
                    <button type="button" className="button ghost" onClick={() => { setEditing({ ...user, is_active: String(user.is_active) }); setOpen(true) }}>Editar</button>
                    <button type="button" className="button danger" onClick={() => window.confirm(`Excluir ${user.full_name}?`) && api.deleteUser(user.id).then(load)}>Excluir</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <EntityModal
        open={open}
        title={editing ? 'Editar usuário' : 'Novo usuário'}
        fields={fields}
        initialValues={editing || { role: 'viewer', is_active: 'true' }}
        onClose={() => { setOpen(false); setEditing(null) }}
        onSubmit={save}
      />
    </section>
  )
}
