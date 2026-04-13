import { useEffect, useMemo, useState } from 'react'
import { Pencil, Plus, RefreshCw, Trash2 } from 'lucide-react'

import EntityModal from '../components/EntityModal'
import StatusBadge from '../components/StatusBadge'
import Topbar from '../components/Topbar'
import ViewToggle from '../components/ViewToggle'
import { api } from '../utils/api'
import { canManage } from '../utils/auth'

const fields = [
  { name: 'name', label: 'Nome' },
  { name: 'code', label: 'Codigo' },
  { name: 'city', label: 'Cidade' },
  { name: 'state', label: 'Estado' },
  { name: 'manager_name', label: 'Responsavel' },
  { name: 'manager_phone', label: 'Telefone' },
  { name: 'network_label', label: 'Rede' },
  { name: 'vpn_type', label: 'Tipo de VPN', type: 'select', options: [{ value: 'wireguard', label: 'WireGuard' }, { value: 'l2tp-ipsec', label: 'L2TP/IPsec' }, { value: 'sstp', label: 'SSTP' }, { value: 'openvpn', label: 'OpenVPN' }] },
  { name: 'vpn_host', label: 'Host VPN' },
  { name: 'vpn_port', label: 'Porta VPN', type: 'number' },
  { name: 'vpn_username', label: 'Usuario VPN' },
  { name: 'vpn_password', label: 'Senha VPN', type: 'password' },
  { name: 'vpn_psk', label: 'PSK/IPsec', type: 'password' },
  { name: 'vpn_network_cidr', label: 'Rede remota VPN' },
  { name: 'vpn_adapter_name', label: 'Nome da conexao Windows' },
  { name: 'address', label: 'Endereco', full: true },
  { name: 'notes', label: 'Observacoes', type: 'textarea', full: true },
]

function getUnitOperationalStatus(unit) {
  if (!unit.dvr_count) return 'unknown'
  if (unit.online_dvrs === unit.dvr_count) return 'online'
  if (unit.online_dvrs > 0) return 'warning'
  return 'offline'
}

function getStatusSurfaceClass(status, row = false) {
  if (status === 'offline') return row ? 'status-row-offline' : 'status-surface-offline'
  if (status === 'warning') return row ? 'status-row-warning' : 'status-surface-warning'
  return ''
}

export default function UnitsPage({ refreshToken, connected, currentUser, onLogout }) {
  const [units, setUnits] = useState([])
  const [view, setView] = useState('cards')
  const [search, setSearch] = useState('')
  const [editing, setEditing] = useState(null)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')
  const [scanSummary, setScanSummary] = useState('')
  const [busyUnitId, setBusyUnitId] = useState(null)
  const allowManage = canManage(currentUser)

  const load = async () => {
    try {
      setError('')
      setUnits(await api.listUnits())
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    load()
  }, [refreshToken])

  const filtered = useMemo(
    () => units.filter((unit) => `${unit.name} ${unit.city} ${unit.code}`.toLowerCase().includes(search.toLowerCase())),
    [units, search],
  )

  const save = async (form) => {
    try {
      const payload = {
        ...form,
        vpn_port: form.vpn_port ? Number(form.vpn_port) : null,
      }
      setError('')
      setScanSummary('')
      let savedUnit
      if (editing?.id) {
        savedUnit = await api.updateUnit(editing.id, payload)
      } else {
        savedUnit = await api.createUnit(payload)
      }
      if (savedUnit?.vpn_network_cidr) {
        setBusyUnitId(savedUnit.id)
        try {
          const result = await api.discoverUnitDvrs(savedUnit.id)
          setScanSummary(
            `${savedUnit.name}: ${result.discovered_count} DVRs detectados, ${result.created_count} cadastrados e ${result.updated_count} atualizados. Preencha apenas usuario e senha dos gravadores encontrados.`,
          )
        } catch (err) {
          setError(`Unidade salva, mas a descoberta automatica nao concluiu: ${err.message}`)
        } finally {
          setBusyUnitId(null)
        }
      }
      setOpen(false)
      setEditing(null)
      await load()
    } catch (err) {
      setError(err.message)
      throw err
    }
  }

  const remove = async (unit) => {
    if (!window.confirm(`Excluir ${unit.name}?`)) return
    try {
      setError('')
      await api.deleteUnit(unit.id)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  const scanUnitDvrs = async (unit) => {
    setError('')
    setScanSummary('')
    setBusyUnitId(unit.id)
    try {
      const result = await api.discoverUnitDvrs(unit.id)
      setScanSummary(
        `${unit.name}: ${result.discovered_count} DVRs detectados, ${result.created_count} cadastrados e ${result.updated_count} atualizados. Revise usuario e senha para acesso remoto.`,
      )
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyUnitId(null)
    }
  }

  return (
    <section className="page-shell">
      <Topbar
        title="Cadastro das unidades"
        subtitle="Base mestre das academias, rede local e parametros de OpenVPN ou outros tunéis por unidade."
        connected={connected}
        onRefresh={load}
        currentUser={currentUser}
        onLogout={onLogout}
      />

      <div className="toolbar">
        <input
          className="search-input"
          placeholder="Buscar unidade por nome, cidade ou codigo"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <ViewToggle mode={view} setMode={setView} />
        {allowManage ? (
          <button type="button" className="button primary" onClick={() => { setEditing(null); setOpen(true) }}>
            <Plus size={16} />
            Incluir
          </button>
        ) : null}
      </div>

      {error ? <div className="alert-banner error">{error}</div> : null}
      {scanSummary ? <div className="alert-banner success">{scanSummary}</div> : null}

      {view === 'cards' ? (
        <div className="card-grid unit-summary-grid">
          {filtered.map((unit) => {
            const status = getUnitOperationalStatus(unit)
            return (
              <article key={unit.id} className={`entity-card unit-summary-card ${getStatusSurfaceClass(status)}`.trim()}>
                <div className="entity-card-header unit-summary-header">
                  <div className="unit-summary-title">
                    <strong>{unit.name}</strong>
                    <span>{unit.code} - {unit.city}/{unit.state}</span>
                  </div>
                  <StatusBadge status={status} />
                </div>
                <div className="entity-card-body unit-summary-body">
                  <div className="unit-summary-metrics">
                    <div className="metric-line"><span>DVRs</span><strong>{unit.online_dvrs}/{unit.dvr_count}</strong></div>
                    <div className="metric-line"><span>Cameras</span><strong>{unit.online_cameras}/{unit.camera_count}</strong></div>
                    <div className="metric-line"><span>Ativos</span><strong>{unit.network_asset_count || 0}</strong></div>
                  </div>
                  <div className="unit-summary-network">
                    <span>Rede</span>
                    <strong>{unit.network_label || '-'}</strong>
                  </div>
                  <div className="unit-summary-network">
                    <span>VPN</span>
                    <strong>{unit.vpn_type ? `${unit.vpn_type} / ${unit.has_vpn_password ? 'ok' : 'sem senha'}` : '-'}</strong>
                  </div>
                  <div className="unit-summary-network">
                    <span>Credenciais DVR</span>
                    <strong>{unit.pending_dvr_credentials_count ? `${unit.pending_dvr_credentials_count} pendente(s)` : 'todas ok'}</strong>
                  </div>
                </div>
                {allowManage ? (
                  <div className="entity-card-actions compact-actions unit-summary-actions">
                    <button type="button" className="button ghost" onClick={() => scanUnitDvrs(unit)} disabled={busyUnitId === unit.id}>
                      <RefreshCw size={16} className={busyUnitId === unit.id ? 'spin' : ''} />
                      Mapear DVRs
                    </button>
                    <button type="button" className="button ghost" onClick={() => { setEditing(unit); setOpen(true) }}>
                      <Pencil size={16} />
                      Editar
                    </button>
                    <button type="button" className="button danger" onClick={() => remove(unit)}>
                      <Trash2 size={16} />
                      Deletar
                    </button>
                  </div>
                ) : null}
              </article>
            )
          })}
        </div>
      ) : (
        <div className="table-shell">
          <table>
            <thead>
              <tr>
                <th>Unidade</th>
                <th>Cidade</th>
                <th>DVRs</th>
                <th>Cameras</th>
                <th>Rede</th>
                <th>VPN</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filtered.map((unit) => {
                const status = getUnitOperationalStatus(unit)
                return (
                  <tr key={unit.id} className={getStatusSurfaceClass(status, true)}>
                    <td>
                      <strong>{unit.name}</strong>
                      <span>{unit.code}</span>
                    </td>
                    <td>{unit.city}/{unit.state}</td>
                    <td>{unit.online_dvrs}/{unit.dvr_count}</td>
                    <td>{unit.online_cameras}/{unit.camera_count}</td>
                    <td>{unit.network_label || '-'}</td>
                    <td>{unit.vpn_type || '-'}</td>
                    <td className="actions-cell">
                      {allowManage ? (
                        <>
                          <button type="button" className="button ghost" onClick={() => scanUnitDvrs(unit)} disabled={busyUnitId === unit.id}>Mapear DVRs</button>
                          <button type="button" className="button ghost" onClick={() => { setEditing(unit); setOpen(true) }}>Editar</button>
                          <button type="button" className="button danger" onClick={() => remove(unit)}>Excluir</button>
                        </>
                      ) : null}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {allowManage ? (
        <EntityModal
          open={open}
          title={editing ? 'Editar unidade' : 'Nova unidade'}
          fields={fields}
          initialValues={editing || { state: 'SP', vpn_type: 'openvpn', vpn_port: 1194 }}
          onClose={() => { setOpen(false); setEditing(null) }}
          onSubmit={save}
        />
      ) : null}
    </section>
  )
}
