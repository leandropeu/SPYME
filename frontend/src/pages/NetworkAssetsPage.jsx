import { Copy, GitBranch, Globe, Monitor, Pencil, Plus, Radar, Search, ShieldCheck, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import EntityModal from '../components/EntityModal'
import StatusBadge from '../components/StatusBadge'
import Topbar from '../components/Topbar'
import ViewToggle from '../components/ViewToggle'
import { canManage } from '../utils/auth'
import { formatDate } from '../utils/format'
import { api } from '../utils/api'

const assetTypeOptions = [
  { value: 'mikrotik', label: 'MikroTik' },
  { value: 'router', label: 'Roteador' },
  { value: 'operator-router', label: 'Roteador operadora' },
  { value: 'access-point', label: 'Access Point' },
  { value: 'switch', label: 'Switch' },
  { value: 'catraca', label: 'Catraca' },
  { value: 'facial', label: 'Facial' },
  { value: 'alarm', label: 'Alarme' },
  { value: 'machine', label: 'Computador' },
  { value: 'server', label: 'Servidor' },
  { value: 'dvr', label: 'DVR' },
  { value: 'nvr', label: 'NVR' },
  { value: 'camera', label: 'Camera' },
  { value: 'unknown', label: 'Desconhecido' },
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

function getStatusSurfaceClass(status, row = false) {
  if (status === 'offline') return row ? 'status-row-offline' : 'status-surface-offline'
  if (status === 'warning') return row ? 'status-row-warning' : 'status-surface-warning'
  return ''
}

function TopologyTree({ node, childrenByParent, onCopy }) {
  const children = childrenByParent.get(node.id) || []
  return (
    <div className="topology-tree-node">
      <article className={`topology-node ${getStatusSurfaceClass(node.status)}`.trim()}>
        <div className="topology-node-header">
          <div>
            <strong>{node.label}</strong>
            <span>{node.asset_type}{node.host ? ` • ${node.host}` : ''}</span>
          </div>
          <StatusBadge status={node.status} />
        </div>
        {node.connection_target ? (
          <div className="topology-node-actions">
            <span className="topology-link-label">{node.connection_label}</span>
            <button type="button" className="button ghost" onClick={() => onCopy(node.connection_target)}>
              <Copy size={16} />
              Copiar
            </button>
          </div>
        ) : null}
      </article>
      {children.length ? (
        <div className="topology-children">
          {children.map((child) => <TopologyTree key={child.id} node={child} childrenByParent={childrenByParent} onCopy={onCopy} />)}
        </div>
      ) : null}
    </div>
  )
}

export default function NetworkAssetsPage({ refreshToken, connected, currentUser, onLogout }) {
  const [assets, setAssets] = useState([])
  const [units, setUnits] = useState([])
  const [dvrs, setDvrs] = useState([])
  const [view, setView] = useState('cards')
  const [search, setSearch] = useState('')
  const [unitFilter, setUnitFilter] = useState('')
  const [topology, setTopology] = useState(null)
  const [topologyLoading, setTopologyLoading] = useState(false)
  const [editing, setEditing] = useState(null)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busyAction, setBusyAction] = useState('')
  const [discoveryResult, setDiscoveryResult] = useState(null)
  const allowManage = canManage(currentUser)

  const fields = useMemo(() => {
    const selectedUnitId = editing?.unit_id || unitFilter
    const parentCandidates = assets
      .filter((asset) => String(asset.unit_id) === String(selectedUnitId) && asset.id !== editing?.id)
      .map((asset) => ({ value: String(asset.id), label: `${asset.name} • ${asset.asset_type}` }))
    const filteredDvrs = dvrs
      .filter((dvr) => !selectedUnitId || String(dvr.unit_id) === String(selectedUnitId))
      .map((dvr) => ({ value: String(dvr.id), label: `${dvr.name} • ${dvr.unit_name || ''}` }))

    return [
      { name: 'unit_id', label: 'Unidade', type: 'select', options: units.map((unit) => ({ value: String(unit.id), label: unit.name })) },
      { name: 'parent_asset_id', label: 'Ativo pai / uplink', type: 'select', options: parentCandidates },
      { name: 'dvr_id', label: 'DVR vinculado', type: 'select', options: filteredDvrs },
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
    ]
  }, [assets, dvrs, editing?.id, editing?.unit_id, unitFilter, units])

  const load = async (selectedUnit = unitFilter) => {
    try {
      setError('')
      const [assetData, unitData, dvrData] = await Promise.all([
        api.listNetworkAssets(selectedUnit ? { unitId: selectedUnit } : {}),
        api.listUnits(),
        api.listDvrs(selectedUnit || undefined),
      ])
      setAssets(assetData)
      setUnits(unitData)
      setDvrs(dvrData)
    } catch (err) {
      setError(err.message)
    }
  }

  const loadTopology = async (selectedUnit = unitFilter) => {
    if (!selectedUnit) {
      setTopology(null)
      return
    }
    setTopologyLoading(true)
    try {
      setTopology(await api.getNetworkTopology(selectedUnit))
    } catch (err) {
      setError(err.message)
    } finally {
      setTopologyLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [refreshToken])

  useEffect(() => {
    load(unitFilter)
    loadTopology(unitFilter)
  }, [unitFilter])

  const filtered = useMemo(
    () => assets.filter((item) => `${item.name} ${item.host} ${item.asset_type} ${item.unit_name || ''} ${item.protocol} ${item.vendor || ''}`.toLowerCase().includes(search.toLowerCase())),
    [assets, search],
  )

  const topologyTree = useMemo(() => {
    if (!topology?.nodes?.length) return null
    const childrenByParent = new Map()
    topology.nodes.forEach((node) => {
      const parentKey = node.parent_id || 'root'
      const bucket = childrenByParent.get(parentKey) || []
      bucket.push(node)
      childrenByParent.set(parentKey, bucket)
    })
    return {
      roots: childrenByParent.get('root') || [],
      childrenByParent,
    }
  }, [topology])

  const save = async (form) => {
    const payload = {
      ...form,
      unit_id: Number(form.unit_id),
      dvr_id: form.dvr_id ? Number(form.dvr_id) : null,
      parent_asset_id: form.parent_asset_id ? Number(form.parent_asset_id) : null,
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
    await load(payload.unit_id)
    await loadTopology(payload.unit_id)
    setNotice('Ativo de rede salvo com sucesso.')
  }

  const remove = async (asset) => {
    if (!window.confirm(`Excluir ${asset.name}?`)) return
    await api.deleteNetworkAsset(asset.id)
    await load(unitFilter)
    await loadTopology(unitFilter)
    setNotice('Ativo removido.')
  }

  const copyTarget = async (value) => {
    try {
      await navigator.clipboard.writeText(value)
      setNotice('Destino de conexao copiado.')
      setError('')
    } catch {
      setError('Nao foi possivel copiar o destino.')
    }
  }

  const runCheck = async (asset) => {
    setBusyAction(`check-${asset.id}`)
    setNotice('')
    setError('')
    try {
      await api.checkNetworkAsset(asset.id)
      await load(unitFilter)
      await loadTopology(unitFilter)
      setNotice(`Verificacao do ativo ${asset.name} executada.`)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyAction('')
    }
  }

  const runDiscovery = async () => {
    if (!unitFilter) {
      setError('Selecione uma unidade para rodar a descoberta na rede.')
      return
    }
    setBusyAction('discover')
    setNotice('')
    setError('')
    try {
      const result = await api.discoverNetworkAssets(unitFilter)
      setDiscoveryResult(result)
      await load(unitFilter)
      await loadTopology(unitFilter)
      setNotice(`Descoberta concluida: ${result.discovered_count} host(s), ${result.created_count} novo(s) e ${result.updated_count} atualizado(s).`)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyAction('')
    }
  }

  const selectedUnit = units.find((unit) => String(unit.id) === String(unitFilter))
  const onlineCount = filtered.filter((asset) => asset.status === 'online').length
  const offlineCount = filtered.filter((asset) => asset.status === 'offline').length
  const warningCount = filtered.filter((asset) => asset.status === 'warning').length

  return (
    <section className="page-shell">
      <Topbar
        title="Infraestrutura e OpenVPN"
        subtitle="Mapa operacional da unidade com MikroTik, APs, catracas, faciais, computadores e acessos tecnicos por Web, SSH e RDP."
        connected={connected}
        onRefresh={() => {
          load(unitFilter)
          loadTopology(unitFilter)
        }}
        currentUser={currentUser}
        onLogout={onLogout}
      />

      <div className="toolbar">
        <input className="search-input" placeholder="Buscar por nome, IP, tipo, protocolo ou unidade" value={search} onChange={(event) => setSearch(event.target.value)} />
        <select className="search-input network-unit-filter" value={unitFilter} onChange={(event) => setUnitFilter(event.target.value)}>
          <option value="">Todas as unidades</option>
          {units.map((unit) => <option key={unit.id} value={unit.id}>{unit.name}</option>)}
        </select>
        <ViewToggle mode={view} setMode={setView} />
        {allowManage ? (
          <>
            <button type="button" className="button ghost" disabled={!unitFilter || busyAction === 'discover'} onClick={runDiscovery}>
              <Search size={16} />
              {busyAction === 'discover' ? 'Descobrindo...' : 'Descobrir ativos'}
            </button>
            <button type="button" className="button primary" onClick={() => { setEditing({ unit_id: unitFilter, protocol: 'https', asset_type: 'mikrotik', is_active: 'true' }); setOpen(true) }}>
              <Plus size={16} />
              Novo ativo
            </button>
          </>
        ) : null}
      </div>

      {error ? <div className="alert-banner error">{error}</div> : null}
      {notice ? <div className="alert-banner success">{notice}</div> : null}

      <div className="panel-grid two-columns">
        <section className="panel infrastructure-overview">
          <div className="panel-header">
            <div>
              <span className="eyebrow">Acesso remoto</span>
              <h3>Resumo operacional</h3>
            </div>
            <ShieldCheck size={18} />
          </div>
          <div className="stats-grid infrastructure-stats">
            <div className="stat-card blue"><div className="stat-icon"><Globe size={12} /></div><div><strong>{filtered.length}</strong><span>Ativos filtrados</span></div></div>
            <div className="stat-card green"><div className="stat-icon"><ShieldCheck size={12} /></div><div><strong>{onlineCount}</strong><span>Online</span></div></div>
            <div className="stat-card amber"><div className="stat-icon"><Radar size={12} /></div><div><strong>{warningCount}</strong><span>Alerta</span></div></div>
            <div className="stat-card red"><div className="stat-icon"><Monitor size={12} /></div><div><strong>{offlineCount}</strong><span>Offline</span></div></div>
          </div>
          <div className="stack-list compact-list">
            <div className="info-block">
              <div>
                <strong>VPN da unidade</strong>
                <span>{selectedUnit ? `${selectedUnit.vpn_type || 'Nao definida'} • ${selectedUnit.vpn_host || 'sem host'}${selectedUnit.vpn_port ? `:${selectedUnit.vpn_port}` : ''}` : 'Selecione uma unidade para visualizar a VPN.'}</span>
              </div>
            </div>
            <div className="info-block">
              <div>
                <strong>Desenho recomendado</strong>
                <span>Use a hierarquia operadora → MikroTik/OpenVPN → switch/AP → catraca/facial/PC/DVR. O campo "Ativo pai / uplink" desenha o mapa da unidade.</span>
              </div>
            </div>
          </div>
        </section>

        <section className="panel infrastructure-overview">
          <div className="panel-header">
            <div>
              <span className="eyebrow">Topologia</span>
              <h3>Mapa dos equipamentos interligados</h3>
            </div>
            <GitBranch size={18} />
          </div>
          {unitFilter ? (
            topologyTree?.roots?.length ? (
              <div className="topology-root-list">
                {topologyTree.roots.map((node) => (
                  <TopologyTree key={node.id} node={node} childrenByParent={topologyTree.childrenByParent} onCopy={copyTarget} />
                ))}
              </div>
            ) : (
              <div className="empty-state">
                {topologyLoading ? 'Montando o mapa da unidade...' : 'Nenhum ativo vinculado ainda. Cadastre os equipamentos e use "Ativo pai / uplink" para desenhar a interligacao.'}
              </div>
            )
          ) : (
            <div className="empty-state">Selecione uma unidade para visualizar o mapa de interligacao.</div>
          )}
        </section>
      </div>

      {discoveryResult ? (
        <section className="panel">
          <div className="panel-header">
            <div>
              <span className="eyebrow">Descoberta automatica</span>
              <h3>Ultimo scan da unidade</h3>
            </div>
            <Radar size={18} />
          </div>
          <div className="stack-list compact-list">
            <div className="info-block">
              <div>
                <strong>Resumo</strong>
                <span>{discoveryResult.network_cidr} • scanner {discoveryResult.scanner} • {discoveryResult.discovered_count} host(s) encontrados</span>
              </div>
            </div>
            {discoveryResult.hosts.map((host) => (
              <div key={host.host} className="info-block">
                <div>
                  <strong>{host.host} • {host.name}</strong>
                  <span>{host.asset_type} • {host.protocol}{host.port ? `:${host.port}` : ''} • portas {host.open_ports.join(', ') || 'nao identificadas'}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {view === 'cards' ? (
        <div className="card-grid">
          {filtered.map((asset) => (
            <article key={asset.id} className={`entity-card ${getStatusSurfaceClass(asset.status)}`.trim()}>
              <div className="entity-card-header">
                <div>
                  <strong>{asset.name}</strong>
                  <span>{asset.unit_name} • {asset.asset_type}</span>
                </div>
                <StatusBadge status={asset.status} />
              </div>
              <div className="entity-card-body">
                <div className="metric-line"><span>Acesso</span><strong>{asset.protocol}://{asset.host}{asset.port ? `:${asset.port}` : ''}</strong></div>
                <div className="metric-line"><span>Uplink</span><strong>{asset.parent_asset_name || 'Raiz'}</strong></div>
                <div className="metric-line"><span>Ultima checagem</span><strong>{formatDate(asset.last_checked)}</strong></div>
                <div className="metric-line"><span>Latencia</span><strong>{asset.last_latency_ms ? `${asset.last_latency_ms} ms` : '—'}</strong></div>
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
                    <button type="button" className="button ghost" disabled={busyAction === `check-${asset.id}`} onClick={() => runCheck(asset)}>
                      <Radar size={16} />
                      {busyAction === `check-${asset.id}` ? 'Testando...' : 'Testar'}
                    </button>
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
                <th>Status</th>
                <th>Uplink</th>
                <th>Ultima checagem</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filtered.map((asset) => (
                <tr key={asset.id} className={getStatusSurfaceClass(asset.status, true)}>
                  <td>
                    <strong>{asset.name}</strong>
                    <span>{asset.asset_type} • {asset.protocol}</span>
                  </td>
                  <td>{asset.unit_name}</td>
                  <td>{asset.host}{asset.port ? `:${asset.port}` : ''}</td>
                  <td><StatusBadge status={asset.status} /></td>
                  <td>{asset.parent_asset_name || 'Raiz'}</td>
                  <td>{formatDate(asset.last_checked)}</td>
                  <td className="actions-cell">
                    {asset.connection_target ? <button type="button" className="button ghost" onClick={() => copyTarget(asset.connection_target)}>Copiar</button> : null}
                    {allowManage ? (
                      <>
                        <button type="button" className="button ghost" disabled={busyAction === `check-${asset.id}`} onClick={() => runCheck(asset)}>Testar</button>
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
          title={editing?.id ? 'Editar ativo de rede' : 'Novo ativo de rede'}
          fields={fields}
          initialValues={editing || { asset_type: 'mikrotik', protocol: 'https', is_active: 'true', unit_id: unitFilter || '' }}
          onClose={() => { setOpen(false); setEditing(null) }}
          onSubmit={save}
        />
      ) : null}
    </section>
  )
}
