import { useEffect, useMemo, useState } from 'react'
import { Eye, Link2, Pencil, Plus, Power, Radar, RefreshCw, Trash2 } from 'lucide-react'

import EntityModal from '../components/EntityModal'
import Modal from '../components/Modal'
import StatusBadge from '../components/StatusBadge'
import Topbar from '../components/Topbar'
import ViewToggle from '../components/ViewToggle'
import { api } from '../utils/api'
import { canManage } from '../utils/auth'
import { formatDate } from '../utils/format'

function toApiDateTime(value) {
  return value ? new Date(value).toISOString() : undefined
}

function toBooleanString(value) {
  return value === false ? 'false' : 'true'
}

const INITIAL_CONSOLE_STATE = {
  loading: false,
  recordingsLoading: false,
  error: '',
  notice: '',
  webInfo: null,
  channels: [],
  recordings: [],
  filters: {
    channel: '1',
    start: '',
    end: '',
  },
}

function getStatusSurfaceClass(status, row = false) {
  if (status === 'offline') return row ? 'status-row-offline' : 'status-surface-offline'
  if (status === 'warning') return row ? 'status-row-warning' : 'status-surface-warning'
  return ''
}

function isPlaybackFirmwareLimitation(message) {
  return String(message || '').toLowerCase().includes('firmware hikvision recusou a busca isapi')
}

export default function DvrsPage({ refreshToken, connected, currentUser, onLogout }) {
  const [dvrs, setDvrs] = useState([])
  const [units, setUnits] = useState([])
  const [cloudAccounts, setCloudAccounts] = useState([])
  const [view, setView] = useState('list')
  const [search, setSearch] = useState('')
  const [editing, setEditing] = useState(null)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busyAction, setBusyAction] = useState('')
  const [consoleOpen, setConsoleOpen] = useState(false)
  const [consoleDvr, setConsoleDvr] = useState(null)
  const [consoleState, setConsoleState] = useState(INITIAL_CONSOLE_STATE)
  const [rebootConfirmOpen, setRebootConfirmOpen] = useState(false)
  const allowManage = canManage(currentUser)

  const fields = useMemo(() => [
    { name: 'unit_id', label: 'Unidade', type: 'select', options: units.map((unit) => ({ value: String(unit.id), label: unit.name })) },
    { name: 'name', label: 'Nome do DVR' },
    { name: 'vendor', label: 'Fabricante', type: 'select', options: [{ value: 'hikvision', label: 'Hikvision' }, { value: 'intelbras', label: 'Intelbras' }] },
    { name: 'model', label: 'Modelo' },
    { name: 'serial_number', label: 'Serial do fabricante' },
    { name: 'device_serial', label: 'Serial na nuvem' },
    { name: 'host', label: 'Host/IP' },
    { name: 'port', label: 'Porta', type: 'number' },
    { name: 'protocol', label: 'Protocolo', type: 'select', options: [{ value: 'http', label: 'HTTP' }, { value: 'https', label: 'HTTPS' }] },
    { name: 'username', label: 'Usuário técnico' },
    { name: 'password', label: 'Senha técnica', type: 'password' },
    { name: 'owner_username', label: 'Login proprietário' },
    { name: 'owner_password', label: 'Senha proprietária', type: 'password' },
    { name: 'channel_count', label: 'Canais', type: 'number' },
    { name: 'cloud_account_id', label: 'Conta cloud', type: 'select', options: cloudAccounts.map((account) => ({ value: String(account.id), label: `${account.name} • ${account.vendor}` })) },
    { name: 'api_status_path', label: 'Caminho de status', full: true },
    { name: 'device_info_path', label: 'Caminho de device info', full: true },
    { name: 'is_active', label: 'Ativo', type: 'select', options: [{ value: 'true', label: 'Sim' }, { value: 'false', label: 'Não' }] },
    { name: 'notes', label: 'Observações', type: 'textarea', full: true },
  ], [cloudAccounts, units])

  const load = async () => {
    try {
      setError('')
      const [unitData, dvrData, accountData] = await Promise.all([
        api.listUnits(),
        api.listDvrs(),
        api.listCloudAccounts(),
      ])
      setUnits(unitData)
      setDvrs(dvrData)
      setCloudAccounts(accountData)
    } catch (err) {
      setError(err.message)
    }
  }

  const runDvrAction = async (actionKey, action, successMessage) => {
    setBusyAction(actionKey)
    setError('')
    setNotice('')
    try {
      await action()
      await load()
      setNotice(successMessage)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyAction('')
    }
  }

  useEffect(() => {
    load()
  }, [refreshToken])

  const filtered = useMemo(
    () => dvrs.filter((item) => `${item.name} ${item.host} ${item.vendor} ${item.unit_name || ''}`.toLowerCase().includes(search.toLowerCase())),
    [dvrs, search],
  )

  const save = async (form) => {
    const payload = {
      ...form,
      unit_id: Number(form.unit_id),
      port: Number(form.port || 80),
      channel_count: Number(form.channel_count || 8),
      cloud_account_id: form.cloud_account_id ? Number(form.cloud_account_id) : null,
      is_active: form.is_active !== 'false',
    }

    if (editing?.id) {
      await api.updateDvr(editing.id, payload)
    } else {
      await api.createDvr(payload)
    }
    setOpen(false)
    setEditing(null)
    load()
  }

  const loadRecordings = async (dvr, nextFilters) => {
    setConsoleState((current) => ({ ...current, recordingsLoading: true, error: '', notice: '' }))
    try {
      const data = await api.getDvrRecordings(dvr.id, {
        channel: Number(nextFilters.channel || 1),
        start: toApiDateTime(nextFilters.start),
        end: toApiDateTime(nextFilters.end),
      })
      setConsoleState((current) => ({
        ...current,
        recordingsLoading: false,
        recordings: data.recordings || [],
        filters: nextFilters,
      }))
    } catch (err) {
      setConsoleState((current) => ({
        ...current,
        recordingsLoading: false,
        error: isPlaybackFirmwareLimitation(err.message) ? '' : err.message,
        notice: isPlaybackFirmwareLimitation(err.message)
          ? 'Este DVR exige playback pela interface nativa. Use "Abrir interface" para consultar gravacoes neste modelo.'
          : '',
      }))
    }
  }

  const openConsole = async (dvr) => {
    setConsoleDvr(dvr)
    setConsoleOpen(true)
    setConsoleState({ ...INITIAL_CONSOLE_STATE, loading: true })

    const [webInfoResult, channelResult, recordingResult] = await Promise.allSettled([
      api.getDvrWebUrl(dvr.id),
      api.getDvrChannels(dvr.id),
      api.getDvrRecordings(dvr.id, { channel: 1 }),
    ])

    const webInfo = webInfoResult.status === 'fulfilled' ? webInfoResult.value : null
    const channels = channelResult.status === 'fulfilled' ? (channelResult.value.channels || []) : []
    const recordings = recordingResult.status === 'fulfilled' ? (recordingResult.value.recordings || []) : []

    const blockingError = webInfoResult.status === 'rejected'
      ? webInfoResult.reason.message
      : channelResult.status === 'rejected'
        ? channelResult.reason.message
        : ''

    const notice = recordingResult.status === 'rejected'
      ? (
        isPlaybackFirmwareLimitation(recordingResult.reason.message)
          ? 'Este DVR exige playback pela interface nativa. Use "Abrir interface" para consultar gravacoes neste modelo.'
          : `Consulta inicial de gravações indisponível: ${recordingResult.reason.message}`
      )
      : ''

    setConsoleState({
      loading: false,
      recordingsLoading: false,
      error: blockingError,
      notice,
      webInfo,
      channels,
      recordings,
      filters: {
        channel: '1',
        start: '',
        end: '',
      },
    })
  }

  const closeConsole = () => {
    setConsoleOpen(false)
    setConsoleDvr(null)
    setConsoleState(INITIAL_CONSOLE_STATE)
    setRebootConfirmOpen(false)
  }

  const runConsoleAction = async (action, successMessage) => {
    if (!consoleDvr) return
    setConsoleState((current) => ({ ...current, loading: true, error: '', notice: '' }))
    try {
      await action()
      await load()
      setConsoleState((current) => ({ ...current, loading: false, notice: successMessage }))
    } catch (err) {
      setConsoleState((current) => ({ ...current, loading: false, error: err.message }))
    }
  }

  return (
    <section className="page-shell">
      <Topbar
        title="DVRs e gravadores"
        subtitle="Cadastro técnico, integração remota, canais e acesso às gravações do equipamento."
        connected={connected}
        onRefresh={load}
        currentUser={currentUser}
        onLogout={onLogout}
      />

      <div className="toolbar">
        <input className="search-input" placeholder="Buscar por nome, IP, fabricante ou unidade" value={search} onChange={(event) => setSearch(event.target.value)} />
        <ViewToggle mode={view} setMode={setView} />
        {allowManage ? (
          <button type="button" className="button primary" onClick={() => { setEditing(null); setOpen(true) }}>
            <Plus size={16} />
            Incluir
          </button>
        ) : null}
      </div>

      {error ? <div className="alert-banner error">{error}</div> : null}
      {notice ? <div className="alert-banner success">{notice}</div> : null}

      {view === 'cards' ? (
        <div className="card-grid">
          {filtered.map((item) => (
            <article key={item.id} className={`entity-card ${getStatusSurfaceClass(item.status)}`.trim()}>
              <div className="entity-card-header">
                <div>
                  <strong>{item.name}</strong>
                  <span>{item.unit_name} • {item.vendor}</span>
                </div>
                <StatusBadge status={item.status} />
              </div>
              <div className="entity-card-body">
                <div className="metric-line"><span>Host</span><strong>{item.host}:{item.port}</strong></div>
                <div className="metric-line"><span>Câmeras instaladas</span><strong>{item.camera_count}</strong></div>
                <div className="metric-line"><span>Capacidade</span><strong>{item.channel_count} canais</strong></div>
                <div className="metric-line"><span>Última checagem</span><strong>{formatDate(item.last_checked)}</strong></div>
              </div>
              <div className="entity-card-actions wrap">
                <button type="button" className="button primary" onClick={() => openConsole(item)}><Eye size={16} />Console</button>
                {allowManage ? (
                  <>
                    <button
                      type="button"
                      className="button ghost"
                      disabled={busyAction === `check-${item.id}` || busyAction === `sync-${item.id}`}
                      onClick={() => runDvrAction(`check-${item.id}`, () => api.checkDvr(item.id), 'Checagem manual executada.')}
                    >
                      <Radar size={16} />
                      {busyAction === `check-${item.id}` ? 'Checando...' : 'Checar'}
                    </button>
                    <button
                      type="button"
                      className="button warning"
                      disabled={busyAction === `sync-${item.id}` || busyAction === `check-${item.id}`}
                      onClick={() => runDvrAction(`sync-${item.id}`, () => api.syncDvrCameras(item.id), 'Sincronização concluída.')}
                    >
                      <Link2 size={16} />
                      {busyAction === `sync-${item.id}` ? 'Sincronizando...' : 'Sincronizar'}
                    </button>
                    <button type="button" className="button ghost" onClick={() => { setEditing({ ...item, is_active: toBooleanString(item.is_active) }); setOpen(true) }}><Pencil size={16} />Editar</button>
                    <button type="button" className="button danger" onClick={() => window.confirm(`Excluir ${item.name}?`) && api.deleteDvr(item.id).then(load)}><Trash2 size={16} />Excluir</button>
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
                <th>DVR</th>
                <th>Unidade</th>
                <th>Host</th>
                <th>Status</th>
                <th>Última checagem</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => (
                <tr key={item.id} className={getStatusSurfaceClass(item.status, true)}>
                  <td>
                    <strong>{item.name}</strong>
                    <span>{item.vendor}</span>
                  </td>
                  <td>{item.unit_name}</td>
                  <td>{item.host}:{item.port}</td>
                  <td><StatusBadge status={item.status} /></td>
                  <td>{formatDate(item.last_checked)}</td>
                  <td className="actions-cell">
                    <button type="button" className="button primary" onClick={() => openConsole(item)}><Eye size={16} /></button>
                    {allowManage ? (
                      <>
                        <button
                          type="button"
                          className="button ghost"
                          disabled={busyAction === `check-${item.id}`}
                          onClick={() => runDvrAction(`check-${item.id}`, () => api.checkDvr(item.id), 'Checagem manual executada.')}
                        >
                          <RefreshCw size={16} />
                        </button>
                        <button type="button" className="button ghost" onClick={() => { setEditing({ ...item, is_active: toBooleanString(item.is_active) }); setOpen(true) }}>Editar</button>
                        <button type="button" className="button danger" onClick={() => window.confirm(`Excluir ${item.name}?`) && api.deleteDvr(item.id).then(load)}>Excluir</button>
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
          title={editing ? 'Editar DVR' : 'Novo DVR'}
          fields={fields}
          initialValues={editing || { vendor: 'hikvision', port: 80, protocol: 'http', channel_count: 8, username: 'admin', is_active: 'true' }}
          onClose={() => { setOpen(false); setEditing(null) }}
          onSubmit={save}
        />
      ) : null}

      <Modal
        open={consoleOpen}
        title={consoleDvr ? `Console do DVR • ${consoleDvr.name}` : 'Console do DVR'}
        onClose={closeConsole}
        className={`wide-modal ${getStatusSurfaceClass(consoleDvr?.status)}`.trim()}
      >
        {consoleState.error ? <div className="alert-banner error">{consoleState.error}</div> : null}
        {consoleState.notice ? <div className="alert-banner success">{consoleState.notice}</div> : null}

        <div className="panel-grid two-columns media-grid">
          <section className={`panel ${getStatusSurfaceClass(consoleDvr?.status)}`.trim()}>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Acesso rápido</span>
                <h3>Conexão e interface</h3>
              </div>
              <StatusBadge status={consoleDvr?.status || 'unknown'} />
            </div>

            <div className="stack-list compact-list">
              <div className="info-block">
                <span>Host</span>
                <strong>{consoleDvr ? `${consoleDvr.host}:${consoleDvr.port}` : '—'}</strong>
              </div>
              <div className="info-block">
                <span>Última checagem</span>
                <strong>{formatDate(consoleDvr?.last_checked)}</strong>
              </div>
              <div className="info-block">
                <span>Conta cloud</span>
                <strong>{consoleDvr?.cloud_account?.name || 'Sem vínculo'}</strong>
              </div>
            </div>

            <div className="entity-card-actions wrap compact-actions">
              {consoleState.webInfo?.url ? (
                <a className="button primary" href={consoleState.webInfo.url} target="_blank" rel="noreferrer">
                  <Eye size={16} />
                  Abrir interface
                </a>
              ) : null}
              {allowManage && consoleDvr ? (
                <>
                  <button type="button" className="button ghost" disabled={consoleState.loading} onClick={() => runConsoleAction(() => api.checkDvr(consoleDvr.id), 'Checagem manual executada.')}>
                    <Radar size={16} />
                    Testar conexão
                  </button>
                  <button type="button" className="button warning" disabled={consoleState.loading} onClick={() => runConsoleAction(() => api.syncDvrCameras(consoleDvr.id), 'Canais sincronizados com sucesso.')}>
                    <Link2 size={16} />
                    Sincronizar câmeras
                  </button>
                  {currentUser?.role === 'admin' ? (
                    <button type="button" className="button danger" disabled={consoleState.loading} onClick={() => setRebootConfirmOpen(true)}>
                      <Power size={16} />
                      Reiniciar DVR
                    </button>
                  ) : null}
                </>
              ) : null}
            </div>

            <div className="stream-box">
              {consoleState.notice || 'Use "Abrir interface" para acessar a tela nativa do DVR para configuração, monitoramento e playback.'}
            </div>
          </section>

          <section className={`panel ${getStatusSurfaceClass(consoleDvr?.status)}`.trim()}>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Topologia</span>
                <h3>Canais detectados</h3>
              </div>
            </div>

            <div className="channel-grid">
              {consoleState.channels.length ? consoleState.channels.map((channel) => (
                <div key={`${channel.id}-${channel.name}`} className="channel-pill">
                  <strong>{channel.name || `Canal ${channel.id}`}</strong>
                  <span>ID {channel.id} • {channel.enabled === 'false' ? 'desabilitado' : 'ativo'}</span>
                </div>
              )) : (
                <div className="empty-state">
                  {consoleState.loading ? 'Consultando canais do DVR...' : 'Nenhum canal retornado por este equipamento.'}
                </div>
              )}
            </div>
          </section>
        </div>

        <section className="panel">
          <div className="panel-header">
            <div>
              <span className="eyebrow">Gravações</span>
              <h3>Consulta e reprodução assistida</h3>
            </div>
          </div>

          <form
            className="recordings-toolbar"
            onSubmit={(event) => {
              event.preventDefault()
              if (consoleDvr) {
                loadRecordings(consoleDvr, consoleState.filters)
              }
            }}
          >
            <label>
              <span>Canal</span>
              <input
                type="number"
                min="1"
                value={consoleState.filters.channel}
                onChange={(event) => setConsoleState((current) => ({ ...current, filters: { ...current.filters, channel: event.target.value } }))}
              />
            </label>
            <label>
              <span>Início</span>
              <input
                type="datetime-local"
                value={consoleState.filters.start}
                onChange={(event) => setConsoleState((current) => ({ ...current, filters: { ...current.filters, start: event.target.value } }))}
              />
            </label>
            <label>
              <span>Fim</span>
              <input
                type="datetime-local"
                value={consoleState.filters.end}
                onChange={(event) => setConsoleState((current) => ({ ...current, filters: { ...current.filters, end: event.target.value } }))}
              />
            </label>
            <button type="submit" className="button primary" disabled={consoleState.recordingsLoading}>
              {consoleState.recordingsLoading ? 'Consultando...' : 'Buscar gravações'}
            </button>
          </form>

          <div className="recording-list">
            {consoleState.recordings.length ? consoleState.recordings.map((recording, index) => (
              <article key={`${recording.start || 'recording'}-${index}`} className="recording-row">
                <div className="recording-meta">
                  <strong>{recording.type || 'Clip'}</strong>
                  <span>Início: {formatDate(recording.start)}</span>
                  <span>Fim: {formatDate(recording.end)}</span>
                </div>
                <div className="entity-card-actions wrap">
                  {recording.playback_url && consoleDvr ? (
                    <>
                      <a className="button ghost" href={api.dvrRecordingProxyUrl(consoleDvr.id, recording.playback_url)} target="_blank" rel="noreferrer">
                        <Eye size={16} />
                        Reproduzir
                      </a>
                      <a className="button ghost" href={api.dvrRecordingProxyUrl(consoleDvr.id, recording.playback_url, true)} target="_blank" rel="noreferrer">
                        <Link2 size={16} />
                        Baixar
                      </a>
                    </>
                  ) : (
                    <span className="empty-state inline-empty">Este fabricante não expôs URL direta de playback para o clip.</span>
                  )}
                </div>
              </article>
            )) : (
              <div className="empty-state">
                {consoleState.recordingsLoading ? 'Consultando gravações do DVR...' : 'Nenhuma gravação encontrada para os filtros atuais.'}
              </div>
            )}
          </div>
        </section>
      </Modal>

      <Modal open={rebootConfirmOpen} title="Confirmar reinicialização" onClose={() => setRebootConfirmOpen(false)}>
        <div className="stack-list compact-list">
          <div className="alert-banner error">
            Esta ação vai reiniciar o DVR{consoleDvr ? ` ${consoleDvr.name}` : ''} e pode interromper temporariamente o monitoramento e a visualização ao vivo.
          </div>
          <div className="info-block">
            <span>Procedimento</span>
            <strong>Deseja realmente continuar com a reinicialização do equipamento?</strong>
          </div>
          <div className="entity-card-actions wrap compact-actions">
            <button type="button" className="button ghost" onClick={() => setRebootConfirmOpen(false)}>
              Cancelar
            </button>
            <button
              type="button"
              className="button danger"
              disabled={consoleState.loading || !consoleDvr}
              onClick={async () => {
                setRebootConfirmOpen(false)
                if (!consoleDvr) return
                await runConsoleAction(() => api.rebootDvr(consoleDvr.id), 'Comando de reboot enviado ao DVR.')
              }}
            >
              Confirmar reinicialização
            </button>
          </div>
        </div>
      </Modal>
    </section>
  )
}
