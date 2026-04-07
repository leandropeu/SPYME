import { Copy, Pencil, Plus, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import EntityModal from '../components/EntityModal'
import Topbar from '../components/Topbar'
import ViewToggle from '../components/ViewToggle'
import { api } from '../utils/api'
import { canManage } from '../utils/auth'

const assetTypeOptions = [
  { value: 'dvr', label: 'DVR' },
  { value: 'nvr', label: 'NVR' },
  { value: 'camera', label: 'Camera' },
  { value: 'router', label: 'Roteador' },
  { value: 'access-point', label: 'Access Point' },
  { value: 'machine', label: 'Maquina' },
  { value: 'switch', label: 'Switch' },
  { value: 'server', label: 'Servidor' },
  { value: 'device', label: 'Outro' },
]

const protocolOptions = [
  { value: 'https', label: 'HTTPS' },
  { value: 'http', label: 'HTTP' },
  { value: 'ssh', label: 'SSH' },
  { value: 'rdp', label: 'RDP' },
  { value: 'rtsp', label: 'RTSP' },
  { value: 'winbox', label: 'WinBox' },
]

export default function NetworkAssetsPage({ refreshToken, connected, currentUser, onLogout }) {
  const [assets, setAssets] = useState([])
  const [units, setUnits] = useState([])
  const [dvrs, setDvrs] = useState([])
  const [view, setView] = useState('cards')
  const [search, setSearch] = useState('')
  const [editing, setEditing] = useState(null)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const allowManage = canManage(currentUser)

  const fields = useMemo(() => [
    { name: 'unit_id', label: 'Unidade', type: 'select', options: units.map((unit) => ({ value: String(unit.id), label: unit.name })) },
    { name: 'dvr_id', label: 'DVR vinculado', type: 'select', options: [{ value: '', label: 'Nenhum' }, ...dvrs.map((dvr) => ({ value: String(dvr.id), label: `${dvr.name} - ${dvr.unit_name || ''}` }))] },
    { name: 'name', label: 'Nome do ativo' },
    { name: 'asset_type', label: 'Tipo', type: 'select', options: assetTypeOptions },
    { name: 'vendor', label: 'Fabricante' },
    { name: 'model', label: 'Modelo' },
    { name: 'host', label: 'Host/IP' },
    { name: 'port', label: 'Porta', type: 'number' },
    { name: 'protocol', label: 'Protocolo', type: 'select', options: protocolOptions },
    { name: 'username', label: 'Usuario' },
    { name: 'password', label: 'Senha', type: 'password' },
    { name: 'path', label: 'Caminho/endpoint' },
    { name: 'mac_address', label: 'MAC' },
    { name: 'local_network', label: 'Rede local/CIDR' },
    { name: 'is_active', label: 'Ativo', type: 'select', options: [{ value: 'true', label: 'Sim' }, { value: 'false', label: 'Nao' }] },
    { name: 'notes', label: 'Observacoes', type: 'textarea', full: true },
  ], [dvrs, units])

  const load = async () => {
    try {
      setError('')
      const [assetData, unitData, dvrData] = await Promise.all([
        api.listNetworkAssets(),
        api.listUnits(),
        api.listDvrs(),
      ])
      setAssets(assetData)
      setUnits(unitData)
      setDvrs(dvrData)
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    load()
  }, [refreshToken])

  const filtered = useMemo(
    () => assets.filter((item) => `${item.name} ${item.host} ${item.asset_type} ${item.unit_name || ''} ${item.protocol}`.toLowerCase().includes(search.toLowerCase())),
    [assets, search],
  )

  const save = async (form) => {
    const payload = {
      ...form,
      unit_id: Number(form.unit_id),
      dvr_id: form.dvr_id ? Number(form.dvr_id) : null,
      port: form.port ? Number(form.port) : null,
      is_active: form.is_active !== 'false',
    }
    if (editing?.id) {
      await api.updateNetworkAsset(editing.id, payload)
    } else {
      await api.createNetworkAsset(payload)
    }
    setOpen(false)
    setEditing(null)
    await load()
  }

  const remove = async (asset) => {
    if (!window.confirm(`Excluir ${asset.name}?`)) return
    await api.deleteNetworkAsset(asset.id)
    await load()
  }

  const copyTarget = async (value) => {
    try {
      await navigator.clipboard.writeText(value)
      setNotice('Destino de conexao copiado.')
    } catch {
      setError('Nao foi possivel copiar o destino.')
    }
  }

  return (
    <section className="page-shell">
      <Topbar
        title="Ativos de rede"
        subtitle="Central tecnica por unidade para DVR, NVR, cameras, roteadores, APs e maquinas com protocolo de acesso."
        connected={connected}
        onRefresh={load}
        currentUser={currentUser}
        onLogout={onLogout}
      />

      <div className="toolbar">
        <input className="search-input" placeholder="Buscar por nome, IP, tipo, protocolo ou unidade" value={search} onChange={(event) => setSearch(event.target.value)} />
        <ViewToggle mode={view} setMode={setView} />
        {allowManage ? (
          <button type="button" className="button primary" onClick={() => { setEditing(null); setOpen(true) }}>
            <Plus size={16} />
            Novo ativo
          </button>
        ) : null}
      </div>

      {error ? <div className="alert-banner error">{error}</div> : null}
      {notice ? <div className="alert-banner success">{notice}</div> : null}

      {view === 'cards' ? (
        <div className="card-grid">
          {filtered.map((asset) => (
            <article key={asset.id} className="entity-card">
              <div className="entity-card-header">
                <div>
                  <strong>{asset.name}</strong>
                  <span>{asset.unit_name} - {asset.asset_type}</span>
                </div>
              </div>
              <div className="entity-card-body">
                <div className="metric-line"><span>Acesso</span><strong>{asset.protocol}://{asset.host}{asset.port ? `:${asset.port}` : ''}</strong></div>
                <div className="metric-line"><span>Usuario</span><strong>{asset.username || '-'}</strong></div>
                <div className="metric-line"><span>Senha</span><strong>{asset.has_password ? 'Configurada' : 'Ausente'}</strong></div>
                <div className="metric-line"><span>Comando</span><strong>{asset.connection_label || '-'}</strong></div>
                {asset.connection_target ? <div className="stream-box">{asset.connection_target}</div> : null}
              </div>
              <div className="entity-card-actions wrap">
                {asset.connection_target ? (
                  <button type="button" className="button ghost" onClick={() => copyTarget(asset.connection_target)}>
                    <Copy size={16} />
                    Copiar acesso
                  </button>
                ) : null}
                {allowManage ? (
                  <>
                    <button type="button" className="button ghost" onClick={() => { setEditing({ ...asset, is_active: asset.is_active === false ? 'false' : 'true' }); setOpen(true) }}>
                      <Pencil size={16} />
                      Editar
                    </button>
                    <button type="button" className="button danger" onClick={() => remove(asset)}>
                      <Trash2 size={16} />
                      Excluir
                    </button>
                  </>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="table-shell">
          <table>
            <thead>
              <tr>
                <th>Ativo</th>
                <th>Unidade</th>
                <th>Host</th>
                <th>Protocolo</th>
                <th>Senha</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filtered.map((asset) => (
                <tr key={asset.id}>
                  <td>
                    <strong>{asset.name}</strong>
                    <span>{asset.asset_type}</span>
                  </td>
                  <td>{asset.unit_name}</td>
                  <td>{asset.host}{asset.port ? `:${asset.port}` : ''}</td>
                  <td>{asset.protocol}</td>
                  <td>{asset.has_password ? 'Configurada' : 'Ausente'}</td>
                  <td className="actions-cell">
                    {asset.connection_target ? <button type="button" className="button ghost" onClick={() => copyTarget(asset.connection_target)}>Copiar</button> : null}
                    {allowManage ? (
                      <>
                        <button type="button" className="button ghost" onClick={() => { setEditing({ ...asset, is_active: asset.is_active === false ? 'false' : 'true' }); setOpen(true) }}>Editar</button>
                        <button type="button" className="button danger" onClick={() => remove(asset)}>Excluir</button>
                      </>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {allowManage ? (
        <EntityModal
          open={open}
          title={editing ? 'Editar ativo de rede' : 'Novo ativo de rede'}
          fields={fields}
          initialValues={editing || { asset_type: 'device', protocol: 'https', is_active: 'true' }}
          onClose={() => { setOpen(false); setEditing(null) }}
          onSubmit={save}
        />
      ) : null}
    </section>
  )
}
