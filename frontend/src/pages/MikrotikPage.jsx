import { Copy, ExternalLink, Router, ShieldCheck, TerminalSquare } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import StatusBadge from '../components/StatusBadge'
import Topbar from '../components/Topbar'
import { api } from '../utils/api'
import { formatDate } from '../utils/format'

const SPYGYM_VPN_SERVER_IP = '10.45.0.1'
const SPYGYM_VPN_MGMT_CIDR = '10.45.0.0/24'

function buildWinboxTarget(asset) {
  if (!asset.host) return ''
  return `${asset.host}:8291`
}

function buildWebfigTarget(asset) {
  if (!asset.host) return ''
  const isHttps = asset.protocol === 'https' || asset.port === 443
  const protocol = isHttps ? 'https' : 'http'
  const defaultPort = isHttps ? 443 : 80
  const port = asset.port && asset.port !== defaultPort ? `:${asset.port}` : ''
  return `${protocol}://${asset.host}${port}`
}

function buildSshTarget(asset) {
  if (!asset.host) return ''
  const userPrefix = asset.username ? `${asset.username}@` : ''
  const port = asset.port && asset.port !== 22 ? ` -p ${asset.port}` : ''
  return `ssh ${userPrefix}${asset.host}${port}`
}

function buildMikrotikMgmtScript(asset, unit) {
  const unitLabel = unit ? `${unit.code} - ${unit.name}` : asset?.unit_name || 'unidade selecionada'
  return [
    `# Liberacao de gestao SPYGYM para ${unitLabel}`,
    '/ip firewall address-list',
    `add list=spygym-mgmt address=${SPYGYM_VPN_SERVER_IP} comment="SPYGYM VPS via OpenVPN ROS6"`,
    `add list=spygym-mgmt address=${SPYGYM_VPN_MGMT_CIDR} comment="Rede VPN SPYGYM ROS6"`,
    '',
    '/ip service',
    `set winbox disabled=no port=8291 address=${SPYGYM_VPN_MGMT_CIDR}`,
    `set www disabled=no port=80 address=${SPYGYM_VPN_MGMT_CIDR}`,
    `set www-ssl disabled=no port=443 address=${SPYGYM_VPN_MGMT_CIDR}`,
    `set ssh disabled=no port=22 address=${SPYGYM_VPN_MGMT_CIDR}`,
    '',
    '/ip firewall filter',
    'add chain=input action=accept src-address-list=spygym-mgmt protocol=tcp dst-port=8291,80,443,22 comment="SPYGYM mgmt via VPN"',
    'add chain=input action=accept src-address-list=spygym-mgmt protocol=icmp comment="SPYGYM ping via VPN"',
    '',
    '# Validacao',
    '# /ip service print',
    '# /ip firewall filter print where comment~"SPYGYM"',
    `# /ping ${SPYGYM_VPN_SERVER_IP}`,
  ].join('\n')
}

export default function MikrotikPage({ refreshToken, connected, currentUser, onLogout }) {
  const [assets, setAssets] = useState([])
  const [units, setUnits] = useState([])
  const [unitFilter, setUnitFilter] = useState('')
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = async () => {
    try {
      setError('')
      const [assetData, unitData] = await Promise.all([
        api.listNetworkAssets(),
        api.listUnits(),
      ])
      setAssets(assetData)
      setUnits(unitData)
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    load()
  }, [refreshToken])

  const mikrotiks = useMemo(() => assets.filter((asset) => {
    const byType = asset.asset_type === 'mikrotik'
    const byVendor = (asset.vendor || '').toLowerCase().includes('mikrotik')
    return byType || byVendor
  }), [assets])

  const filtered = useMemo(() => mikrotiks.filter((asset) => {
    const matchesUnit = !unitFilter || String(asset.unit_id) === String(unitFilter)
    const matchesSearch = `${asset.name} ${asset.host} ${asset.unit_name || ''} ${asset.username || ''}`.toLowerCase().includes(search.toLowerCase())
    return matchesUnit && matchesSearch
  }), [mikrotiks, search, unitFilter])

  const selectedUnit = units.find((unit) => String(unit.id) === String(unitFilter))
  const focusAsset = filtered[0] || null
  const generatedScript = focusAsset ? buildMikrotikMgmtScript(focusAsset, selectedUnit) : ''

  const copyTarget = async (value, label) => {
    try {
      await navigator.clipboard.writeText(value)
      setNotice(`${label} copiado.`)
      setError('')
    } catch {
      setError(`Nao foi possivel copiar ${label.toLowerCase()}.`)
    }
  }

  const openWebfig = (asset) => {
    const url = api.networkAssetProxyUrl(asset.id, asset.path || '/')
    window.open(url, '_blank', 'noopener,noreferrer')
  }

  return (
    <section className="page-shell">
      <Topbar
        title="Acesso MikroTik"
        subtitle="Painel dedicado para WinBox, WebFig e SSH dos MikroTiks das unidades."
        connected={connected}
        onRefresh={load}
        currentUser={currentUser}
        onLogout={onLogout}
      />

      <div className="toolbar">
        <input
          className="search-input"
          placeholder="Buscar por unidade, nome, IP ou usuario"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <select className="search-input network-unit-filter" value={unitFilter} onChange={(event) => setUnitFilter(event.target.value)}>
          <option value="">Todas as unidades</option>
          {units.map((unit) => <option key={unit.id} value={unit.id}>{unit.name}</option>)}
        </select>
      </div>

      {error ? <div className="alert-banner error">{error}</div> : null}
      {notice ? <div className="alert-banner success">{notice}</div> : null}

      <div className="panel-grid two-columns">
        <section className="panel infrastructure-overview">
          <div className="panel-header">
            <div>
              <span className="eyebrow">VPN</span>
              <h3>Contexto da unidade</h3>
            </div>
            <ShieldCheck size={18} />
          </div>
          <div className="stack-list compact-list">
            <div className="info-block">
              <div>
                <strong>Unidade selecionada</strong>
                <span>{selectedUnit ? `${selectedUnit.code} - ${selectedUnit.name}` : 'Selecione uma unidade para focar nos acessos.'}</span>
              </div>
            </div>
            <div className="info-block">
              <div>
                <strong>VPN cadastrada</strong>
                <span>{selectedUnit ? `${selectedUnit.vpn_type || 'Nao definida'} • ${selectedUnit.vpn_host || 'sem host'}${selectedUnit.vpn_port ? `:${selectedUnit.vpn_port}` : ''}` : 'Filtro geral sem unidade selecionada.'}</span>
              </div>
            </div>
            <div className="info-block">
              <div>
                <strong>Rede remota</strong>
                <span>{selectedUnit?.vpn_network_cidr || 'Nao informada.'}</span>
              </div>
            </div>
          </div>
        </section>

        <section className="panel infrastructure-overview">
          <div className="panel-header">
            <div>
              <span className="eyebrow">Inventario</span>
              <h3>MikroTiks vinculados</h3>
            </div>
            <Router size={18} />
          </div>
          <div className="stats-grid infrastructure-stats">
            <div className="stat-card blue"><div><strong>{filtered.length}</strong><span>No filtro atual</span></div></div>
            <div className="stat-card green"><div><strong>{filtered.filter((asset) => asset.status === 'online').length}</strong><span>Online</span></div></div>
            <div className="stat-card amber"><div><strong>{filtered.filter((asset) => asset.status === 'warning').length}</strong><span>Alerta</span></div></div>
            <div className="stat-card red"><div><strong>{filtered.filter((asset) => asset.status === 'offline').length}</strong><span>Offline</span></div></div>
          </div>
        </section>

        <section className="panel infrastructure-overview">
          <div className="panel-header">
            <div>
              <span className="eyebrow">RouterOS</span>
              <h3>Liberacao de acesso pela VPN</h3>
            </div>
            <TerminalSquare size={18} />
          </div>
          {focusAsset ? (
            <>
              <div className="stack-list compact-list">
                <div className="info-block">
                  <div>
                    <strong>Roteador em foco</strong>
                    <span>{focusAsset.name} • {focusAsset.host}</span>
                  </div>
                </div>
                <div className="info-block">
                  <div>
                    <strong>Origem de gestao SPYGYM</strong>
                    <span>{SPYGYM_VPN_MGMT_CIDR} • gateway {SPYGYM_VPN_SERVER_IP}</span>
                  </div>
                </div>
                <div className="info-block">
                  <div>
                    <strong>Observacao operacional</strong>
                    <span>Se houver regra de drop no chain input antes destes accepts, mova as regras SPYGYM para cima.</span>
                  </div>
                </div>
              </div>

              <pre className="config-snippet">{generatedScript}</pre>

              <div className="entity-card-actions wrap">
                <button type="button" className="button primary" onClick={() => copyTarget(generatedScript, 'Script RouterOS')}>
                  <Copy size={16} />
                  Copiar script
                </button>
              </div>
            </>
          ) : (
            <div className="empty-state">
              Selecione uma unidade com MikroTik descoberto para gerar o bloco de liberacao de WinBox, WebFig e SSH pela VPN.
            </div>
          )}
        </section>
      </div>

      <div className="card-grid">
        {filtered.map((asset) => {
          const winboxTarget = buildWinboxTarget(asset)
          const webfigTarget = buildWebfigTarget(asset)
          const sshTarget = buildSshTarget(asset)
          return (
            <article key={asset.id} className="entity-card">
              <div className="entity-card-header">
                <div>
                  <strong>{asset.name}</strong>
                  <span>{asset.unit_name} • {asset.host || 'sem IP'}</span>
                </div>
                <StatusBadge status={asset.status} />
              </div>

              <div className="entity-card-body">
                <div className="metric-line"><span>WinBox</span><strong>{winboxTarget || '-'}</strong></div>
                <div className="metric-line"><span>WebFig</span><strong>{webfigTarget || '-'}</strong></div>
                <div className="metric-line"><span>SSH</span><strong>{sshTarget || '-'}</strong></div>
                <div className="metric-line"><span>Ultima checagem</span><strong>{formatDate(asset.last_checked)}</strong></div>
              </div>

              <div className="entity-card-actions wrap">
                {winboxTarget ? (
                  <button type="button" className="button ghost" onClick={() => copyTarget(winboxTarget, 'Destino WinBox')}>
                    <Copy size={16} />
                    Copiar WinBox
                  </button>
                ) : null}
                {webfigTarget ? (
                  <button type="button" className="button primary" onClick={() => openWebfig(asset)}>
                    <ExternalLink size={16} />
                    Abrir WebFig
                  </button>
                ) : null}
                {webfigTarget ? (
                  <button type="button" className="button ghost" onClick={() => copyTarget(webfigTarget, 'URL WebFig')}>
                    <Router size={16} />
                    Copiar WebFig
                  </button>
                ) : null}
                {sshTarget ? (
                  <button type="button" className="button ghost" onClick={() => copyTarget(sshTarget, 'Comando SSH')}>
                    <TerminalSquare size={16} />
                    Copiar SSH
                  </button>
                ) : null}
              </div>
            </article>
          )
        })}
      </div>

      {!filtered.length ? (
        <section className="panel">
          <div className="empty-state">
            Nenhum MikroTik vinculado foi encontrado no filtro atual. Cadastre ou descubra o gateway da unidade em "Ativos de rede".
          </div>
        </section>
      ) : null}
    </section>
  )
}
