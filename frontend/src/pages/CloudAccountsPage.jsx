import { Eye, EyeOff, Pencil, Plus, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import EntityModal from '../components/EntityModal'
import Topbar from '../components/Topbar'
import ViewToggle from '../components/ViewToggle'
import { canManage, isAdmin } from '../utils/auth'
import { api } from '../utils/api'
import { formatDate } from '../utils/format'

const fields = [
  { name: 'name', label: 'Nome da conta' },
  { name: 'vendor', label: 'Fabricante', type: 'select', options: [{ value: 'hikvision', label: 'Hikvision' }, { value: 'intelbras', label: 'Intelbras' }] },
  { name: 'email', label: 'E-mail' },
  { name: 'password', label: 'Senha', type: 'password', full: true },
  { name: 'notes', label: 'Observações', type: 'textarea', full: true },
]

function getStatusSurfaceClass(hasPassword, dvrCount, row = false) {
  if (!hasPassword) return row ? 'status-row-offline' : 'status-surface-offline'
  if (!dvrCount) return row ? 'status-row-warning' : 'status-surface-warning'
  return ''
}

export default function CloudAccountsPage({ refreshToken, connected, currentUser, onLogout }) {
  const [accounts, setAccounts] = useState([])
  const [view, setView] = useState('list')
  const [search, setSearch] = useState('')
  const [editing, setEditing] = useState(null)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [revealed, setRevealed] = useState({})
  const allowManage = canManage(currentUser)
  const allowReveal = isAdmin(currentUser)

  const load = async () => {
    try {
      setError('')
      setNotice('')
      setAccounts(await api.listCloudAccounts())
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    load()
  }, [refreshToken])

  const filtered = useMemo(
    () => accounts.filter((account) => `${account.name} ${account.vendor} ${account.email}`.toLowerCase().includes(search.toLowerCase())),
    [accounts, search],
  )

  const save = async (form) => {
    const payload = { ...form }
    if (!payload.password) {
      delete payload.password
    }

    if (editing?.id) {
      await api.updateCloudAccount(editing.id, payload)
    } else {
      await api.createCloudAccount(payload)
    }

    setOpen(false)
    setEditing(null)
    setRevealed({})
    await load()
  }

  const remove = async (account) => {
    if (!window.confirm(`Excluir a conta ${account.name}?`)) return
    await api.deleteCloudAccount(account.id)
    setRevealed((current) => {
      const next = { ...current }
      delete next[account.id]
      return next
    })
    await load()
  }

  const toggleReveal = async (accountId) => {
    if (revealed[accountId]) {
      setRevealed((current) => {
        const next = { ...current }
        delete next[accountId]
        return next
      })
      return
    }

    try {
      const data = await api.revealCloudAccountPassword(accountId)
      setRevealed((current) => ({ ...current, [accountId]: data.password }))
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <section className="page-shell">
      <Topbar
        title="Contas cloud"
        subtitle="Credenciais centralizadas de Hikvision e Intelbras para vincular DVRs às contas oficiais."
        connected={connected}
        onRefresh={load}
        currentUser={currentUser}
        onLogout={onLogout}
      />

      <div className="toolbar">
        <input className="search-input" placeholder="Buscar por nome, fabricante ou e-mail" value={search} onChange={(event) => setSearch(event.target.value)} />
        <ViewToggle mode={view} setMode={setView} />
        {allowManage ? (
          <button type="button" className="button primary" onClick={() => { setEditing(null); setOpen(true) }}>
            <Plus size={16} />
            Nova conta
          </button>
        ) : null}
      </div>

      {error ? <div className="alert-banner error">{error}</div> : null}
      {notice ? <div className="alert-banner success">{notice}</div> : null}

      {view === 'cards' ? (
        <div className="card-grid">
          {filtered.map((account) => (
            <article key={account.id} className={`entity-card ${getStatusSurfaceClass(account.has_password, account.dvr_count)}`.trim()}>
              <div className="entity-card-header">
                <div>
                  <strong>{account.name}</strong>
                  <span>{account.vendor} • {account.email}</span>
                </div>
              </div>

              <div className="entity-card-body">
                <div className="metric-line"><span>DVRs vinculados</span><strong>{account.dvr_count}</strong></div>
                <div className="metric-line"><span>Senha</span><strong>{account.has_password ? 'Configurada' : 'Ausente'}</strong></div>
                <div className="metric-line"><span>Atualizada</span><strong>{formatDate(account.updated_at)}</strong></div>
                {account.notes ? <div className="stream-box">{account.notes}</div> : null}
                {allowReveal && revealed[account.id] ? <div className="stream-box">{revealed[account.id]}</div> : null}
              </div>

              {(allowManage || allowReveal) ? (
                <div className="entity-card-actions wrap">
                  {allowReveal ? (
                    <button type="button" className="button ghost" onClick={() => toggleReveal(account.id)}>
                      {revealed[account.id] ? <EyeOff size={16} /> : <Eye size={16} />}
                      {revealed[account.id] ? 'Ocultar senha' : 'Revelar senha'}
                    </button>
                  ) : null}
                  {allowManage ? (
                    <>
                      <button type="button" className="button ghost" onClick={() => { setEditing(account); setOpen(true) }}>
                        <Pencil size={16} />
                        Editar
                      </button>
                      <button type="button" className="button danger" onClick={() => remove(account)}>
                        <Trash2 size={16} />
                        Excluir
                      </button>
                    </>
                  ) : null}
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <div className="table-shell">
          <table>
            <thead>
              <tr>
                <th>Conta</th>
                <th>Fabricante</th>
                <th>DVRs</th>
                <th>Senha</th>
                <th>Atualizada</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filtered.map((account) => (
                <tr key={account.id} className={getStatusSurfaceClass(account.has_password, account.dvr_count, true)}>
                  <td>
                    <strong>{account.name}</strong>
                    <span>{account.email}</span>
                  </td>
                  <td>{account.vendor}</td>
                  <td>{account.dvr_count}</td>
                  <td>{account.has_password ? 'Configurada' : 'Ausente'}</td>
                  <td>{formatDate(account.updated_at)}</td>
                  <td className="actions-cell">
                    {allowReveal ? (
                      <button type="button" className="button ghost" onClick={() => toggleReveal(account.id)}>
                        {revealed[account.id] ? 'Ocultar' : 'Senha'}
                      </button>
                    ) : null}
                    {allowManage ? (
                      <>
                        <button type="button" className="button ghost" onClick={() => { setEditing(account); setOpen(true) }}>Editar</button>
                        <button type="button" className="button danger" onClick={() => remove(account)}>Excluir</button>
                      </>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {allowReveal && Object.keys(revealed).length ? (
            <div className="stack-list compact-list">
              {Object.entries(revealed).map(([id, password]) => {
                const account = accounts.find((item) => String(item.id) === String(id))
                return (
                  <div key={id} className="stream-box">
                    {account?.name || `Conta ${id}`}: {password}
                  </div>
                )
              })}
            </div>
          ) : null}
        </div>
      )}

      {allowManage ? (
        <EntityModal
          open={open}
          title={editing ? 'Editar conta cloud' : 'Nova conta cloud'}
          fields={fields}
          initialValues={editing || { vendor: 'hikvision' }}
          onClose={() => { setOpen(false); setEditing(null) }}
          onSubmit={save}
        />
      ) : null}
    </section>
  )
}
