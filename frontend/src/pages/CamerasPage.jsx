import { useEffect, useMemo, useRef, useState } from 'react'
import Hls from 'hls.js'
import { Eye, PlayCircle, Plus, Radio } from 'lucide-react'

import EntityModal from '../components/EntityModal'
import Modal from '../components/Modal'
import StatusBadge from '../components/StatusBadge'
import Topbar from '../components/Topbar'
import ViewToggle from '../components/ViewToggle'
import { api } from '../utils/api'
import { canManage } from '../utils/auth'
import { formatDate } from '../utils/format'

function browserSupportsNativeHls() {
  if (typeof document === 'undefined') {
    return false
  }
  const video = document.createElement('video')
  return Boolean(video.canPlayType('application/vnd.apple.mpegurl'))
}

function getStatusSurfaceClass(status, row = false) {
  if (status === 'offline') return row ? 'status-row-offline' : 'status-surface-offline'
  if (status === 'warning') return row ? 'status-row-warning' : 'status-surface-warning'
  return ''
}

export default function CamerasPage({ refreshToken, connected, currentUser, onLogout }) {
  const [cameras, setCameras] = useState([])
  const [units, setUnits] = useState([])
  const [dvrs, setDvrs] = useState([])
  const [view, setView] = useState('cards')
  const [search, setSearch] = useState('')
  const [editing, setEditing] = useState(null)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [viewerOpen, setViewerOpen] = useState(false)
  const [viewerCamera, setViewerCamera] = useState(null)
  const [viewerDvr, setViewerDvr] = useState(null)
  const [viewerChannels, setViewerChannels] = useState([])
  const [viewerSelectedChannel, setViewerSelectedChannel] = useState(null)
  const [viewerChannelsOpen, setViewerChannelsOpen] = useState(false)
  const [viewerLoading, setViewerLoading] = useState(false)
  const [viewerError, setViewerError] = useState('')
  const [viewerNotice, setViewerNotice] = useState('')
  const [viewerWebUrl, setViewerWebUrl] = useState('')
  const [viewerHlsActive, setViewerHlsActive] = useState(false)
  const [viewerMode, setViewerMode] = useState('live')
  const videoRef = useRef(null)
  const allowManage = canManage(currentUser)
  const nativeHlsSupported = useMemo(() => browserSupportsNativeHls(), [])
  const inlineHlsSupported = nativeHlsSupported || Hls.isSupported()
  const cameraIndex = useMemo(
    () => new Map(cameras.map((camera) => [`${camera.dvr_id}:${camera.channel_number}`, camera])),
    [cameras],
  )
  const dvrIndex = useMemo(() => new Map(dvrs.map((dvr) => [dvr.id, dvr])), [dvrs])

  const fields = useMemo(() => [
    { name: 'unit_id', label: 'Unidade', type: 'select', options: units.map((unit) => ({ value: String(unit.id), label: unit.name })) },
    { name: 'dvr_id', label: 'DVR', type: 'select', options: dvrs.map((dvr) => ({ value: String(dvr.id), label: `${dvr.name} • ${dvr.unit_name}` })) },
    { name: 'name', label: 'Nome da câmera' },
    { name: 'vendor', label: 'Fabricante', type: 'select', options: [{ value: 'hikvision', label: 'Hikvision' }, { value: 'intelbras', label: 'Intelbras' }] },
    { name: 'channel_number', label: 'Canal', type: 'number' },
    { name: 'location', label: 'Local' },
    { name: 'resolution', label: 'Resolução' },
    { name: 'snapshot_path', label: 'Snapshot path', full: true },
    { name: 'snapshot_url', label: 'Snapshot URL', full: true },
    { name: 'stream_path', label: 'Stream path', full: true },
    { name: 'stream_url', label: 'Stream URL', full: true },
    { name: 'notes', label: 'Observações', type: 'textarea', full: true },
  ], [units, dvrs])

  const load = async () => {
    try {
      setError('')
      setNotice('')
      const [unitData, dvrData, cameraData] = await Promise.all([api.listUnits(), api.listDvrs(), api.listCameras()])
      setUnits(unitData)
      setDvrs(dvrData)
      setCameras(cameraData)
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    load()
  }, [refreshToken])

  useEffect(() => {
    if (!viewerHlsActive || !viewerCamera || !videoRef.current) {
      return undefined
    }

    const video = videoRef.current
    const hlsUrl = api.cameraHlsUrl(viewerCamera.id)

    if (nativeHlsSupported) {
      video.src = hlsUrl
      video.load()
      video.play().catch(() => null)
      return () => {
        video.pause()
        video.removeAttribute('src')
        video.load()
      }
    }

    if (!Hls.isSupported()) {
      setViewerError('Este navegador não suporta o player HLS interno. Use a aba de reprodução para abrir o playback web do DVR.')
      return undefined
    }

    const hls = new Hls({
      enableWorker: true,
      lowLatencyMode: true,
    })

    hls.loadSource(hlsUrl)
    hls.attachMedia(video)
    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      video.play().catch(() => null)
    })
    hls.on(Hls.Events.ERROR, (_, data) => {
      if (data?.fatal) {
        setViewerError('Falha ao reproduzir o HLS desta câmera no navegador.')
        hls.destroy()
      }
    })

    return () => {
      hls.destroy()
      video.pause()
      video.removeAttribute('src')
      video.load()
    }
  }, [nativeHlsSupported, viewerCamera, viewerHlsActive])

  const groupedDvrs = useMemo(() => {
    const searchText = search.toLowerCase()
    return dvrs
      .map((dvr) => {
        const dvrCameras = cameras
          .filter((camera) => camera.dvr_id === dvr.id)
          .sort((a, b) => a.channel_number - b.channel_number)
        const searchBlob = `${dvr.name} ${dvr.unit_name || ''} ${dvr.host || ''} ${dvrCameras.map((camera) => `${camera.name} ${camera.location || ''}`).join(' ')}`.toLowerCase()
        return {
          ...dvr,
          cameras: dvrCameras,
          searchBlob,
        }
      })
      .filter((dvr) => dvr.channel_count > 0 || dvr.cameras.length > 0)
      .filter((dvr) => dvr.searchBlob.includes(searchText))
  }, [cameras, dvrs, search])

  const filteredCameras = useMemo(
    () => cameras
      .filter((camera) => `${camera.name} ${camera.location || ''} ${camera.unit_name || ''} ${camera.dvr_name || ''} ${camera.channel_number}`.toLowerCase().includes(search.toLowerCase()))
      .sort((a, b) => a.channel_number - b.channel_number || a.name.localeCompare(b.name)),
    [cameras, search],
  )

  const save = async (form) => {
    const payload = {
      ...form,
      unit_id: Number(form.unit_id),
      dvr_id: form.dvr_id ? Number(form.dvr_id) : null,
      channel_number: Number(form.channel_number || 1),
    }
    if (editing?.id) {
      await api.updateCamera(editing.id, payload)
    } else {
      await api.createCamera(payload)
    }
    setOpen(false)
    setEditing(null)
    load()
  }

  const remove = async (camera) => {
    if (!window.confirm(`Excluir ${camera.name}?`)) return
    await api.deleteCamera(camera.id)
    await load()
  }

  const stopStreamForCamera = async (camera) => {
    if (!camera || !viewerHlsActive) return
    try {
      await api.stopStream(camera.id)
    } catch {
      // Mantemos a troca de canal/modal mesmo se o stop falhar.
    }
  }

  const fallbackChannelsFor = (dvr) =>
    Array.from({ length: dvr.channel_count || 0 }, (_, index) => {
      const channelNumber = index + 1
      const camera = cameraIndex.get(`${dvr.id}:${channelNumber}`)
      return {
        id: String(channelNumber),
        name: camera?.name || `Canal ${channelNumber}`,
        enabled: 'true',
        has_video: Boolean(camera),
      }
    })

  const pickInitialChannel = (dvr, channels) => {
    const withVideo = channels.find((channel) => channel.has_video)
    if (withVideo) {
      return Number(withVideo.id)
    }
    const firstCamera = dvr.cameras[0]
    if (firstCamera) {
      return firstCamera.channel_number
    }
    return Number(channels[0]?.id || 1)
  }

  const activateViewerChannel = async (dvr, channelNumber, mode = 'live') => {
    const nextCamera = cameraIndex.get(`${dvr.id}:${channelNumber}`) || null
    const previousCamera = viewerCamera

    if (previousCamera && previousCamera.id !== nextCamera?.id && viewerHlsActive) {
      await stopStreamForCamera(previousCamera)
      setViewerHlsActive(false)
    }

    setViewerSelectedChannel(channelNumber)
    setViewerCamera(nextCamera)
    setViewerError('')
    setViewerNotice('')
    setViewerMode(mode)

    if (mode !== 'live') {
      if (!nextCamera) {
        setViewerNotice(`Canal ${channelNumber} sem câmera conectada.`)
      }
      return
    }

    if (!nextCamera) {
      setViewerHlsActive(false)
      setViewerNotice(`Canal ${channelNumber} sem câmera conectada.`)
      return
    }

    if (!inlineHlsSupported) {
      setViewerHlsActive(false)
      setViewerNotice('Este navegador não suporta o player interno. Use o modo de reprodução para abrir a interface do DVR.')
      return
    }

    setViewerLoading(true)
    try {
      await api.startStream(nextCamera.id)
      setViewerHlsActive(true)
      setViewerNotice('Carregando vídeo ao vivo. Aguarde alguns segundos.')
    } catch (err) {
      setViewerHlsActive(false)
      setViewerError(err.message)
    } finally {
      setViewerLoading(false)
    }
  }

  const openViewer = async (dvr, initialChannel = null) => {
    setViewerOpen(true)
    setViewerDvr(dvr)
    setViewerCamera(null)
    setViewerChannels([])
    setViewerSelectedChannel(null)
    setViewerChannelsOpen(false)
    setViewerLoading(true)
    setViewerError('')
    setViewerNotice('')
    setViewerWebUrl('')
    setViewerHlsActive(false)
    setViewerMode('live')

    try {
      const [webResult, channelsResult] = await Promise.allSettled([
        api.getDvrWebUrl(dvr.id),
        api.getDvrChannels(dvr.id),
      ])

      if (webResult.status === 'fulfilled') {
        setViewerWebUrl(webResult.value.url || '')
      }

      const channels = channelsResult.status === 'fulfilled'
        ? (channelsResult.value.channels || [])
        : fallbackChannelsFor(dvr)

      setViewerChannels(channels)

      const firstChannel = initialChannel || pickInitialChannel(dvr, channels)
      await activateViewerChannel(dvr, firstChannel, 'live')
    } catch {
      setViewerError('Não foi possível carregar os canais deste DVR no momento.')
    } finally {
      setViewerLoading(false)
    }
  }

  const closeViewer = () => {
    stopStreamForCamera(viewerCamera).catch(() => null)
    setViewerOpen(false)
    setViewerDvr(null)
    setViewerChannels([])
    setViewerSelectedChannel(null)
    setViewerChannelsOpen(false)
    setViewerCamera(null)
    setViewerLoading(false)
    setViewerError('')
    setViewerNotice('')
    setViewerWebUrl('')
    setViewerHlsActive(false)
    setViewerMode('live')
  }

  const toggleViewerMode = async (mode) => {
    if (!viewerDvr || mode === viewerMode) return

    setViewerMode(mode)
    setViewerError('')
    setViewerNotice('')

    if (mode === 'playback') {
      await stopStreamForCamera(viewerCamera)
      setViewerHlsActive(false)
      if (!viewerCamera) {
        setViewerNotice(`Canal ${viewerSelectedChannel} sem câmera conectada.`)
      }
      return
    }

    await activateViewerChannel(viewerDvr, viewerSelectedChannel || pickInitialChannel(viewerDvr, viewerChannels), 'live')
  }

  const openViewerForCamera = async (camera) => {
    const dvr = dvrIndex.get(camera.dvr_id)
    if (!dvr) {
      setError('O DVR desta câmera não foi localizado.')
      return
    }
    await openViewer(dvr, camera.channel_number)
  }

  return (
    <section className="page-shell">
      <Topbar
        title="Malha das câmeras"
        subtitle="Câmeras instaladas, status operacional e acesso rápido à visualização ao vivo."
        connected={connected}
        onRefresh={load}
        currentUser={currentUser}
        onLogout={onLogout}
      />

      <div className="toolbar">
        <input className="search-input" placeholder="Buscar por câmera, setor, unidade ou DVR" value={search} onChange={(event) => setSearch(event.target.value)} />
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
        groupedDvrs.length ? (
          <div className="camera-group-grid">
            {groupedDvrs.map((dvr) => (
              <article key={dvr.id} className={`entity-card camera-group-card ${getStatusSurfaceClass(dvr.status)}`.trim()}>
                <div className="entity-card-header">
                  <div>
                    <strong>{dvr.name}</strong>
                    <span>{dvr.unit_name} • {dvr.host}:{dvr.port}</span>
                  </div>
                  <StatusBadge status={dvr.status} />
                </div>

                <div className="camera-group-metrics">
                  <div className="metric-line"><span>Câmeras conectadas</span><strong>{dvr.camera_count}</strong></div>
                  <div className="metric-line"><span>Capacidade</span><strong>{dvr.channel_count}</strong></div>
                  <div className="metric-line"><span>Última checagem</span><strong>{formatDate(dvr.last_checked)}</strong></div>
                </div>

                <div className="camera-group-strip">
                  {Array.from({ length: dvr.channel_count || 0 }, (_, index) => {
                    const channelNumber = index + 1
                    const camera = cameraIndex.get(`${dvr.id}:${channelNumber}`)
                    return (
                      <button
                        key={`${dvr.id}-${channelNumber}`}
                        type="button"
                        className={`channel-dot ${camera ? 'active' : 'empty'}`}
                        title={camera ? `${camera.name} • Canal ${channelNumber}` : `Canal ${channelNumber} sem câmera`}
                        onClick={() => openViewer(dvr, channelNumber)}
                      >
                        {channelNumber}
                      </button>
                    )
                  })}
                </div>

                <div className="entity-card-actions compact-actions">
                  <button type="button" className="button primary" onClick={() => openViewer(dvr)}>
                    <Radio size={16} />
                    Abrir visualizador
                  </button>
                </div>

                {dvr.cameras.length ? (
                  <div className="stack-list compact-list">
                    {dvr.cameras.slice(0, 4).map((camera) => (
                      <div key={camera.id} className={`info-block ${getStatusSurfaceClass(camera.status)}`.trim()}>
                        <div>
                          <strong>{camera.name}</strong>
                          <span>Canal {camera.channel_number} • {camera.location || 'Sem local informado'}</span>
                        </div>
                        <div className="entity-card-actions compact-actions">
                          <button type="button" className="button ghost" onClick={() => openViewerForCamera(camera)}>
                            <Radio size={16} />
                            Abrir
                          </button>
                          {allowManage ? (
                            <>
                              <button type="button" className="button ghost" onClick={() => { setEditing(camera); setOpen(true) }}>
                                Editar
                              </button>
                              <button type="button" className="button danger" onClick={() => remove(camera)}>
                                Excluir
                              </button>
                            </>
                          ) : null}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            Nenhum DVR com canais disponíveis foi encontrado. Vá para a aba DVRs, sincronize o gravador desejado e depois volte aqui para validar a visualização.
          </div>
        )
      ) : (
        <div className="table-shell">
          <table>
            <thead>
              <tr>
                <th>Câmera</th>
                <th>Unidade</th>
                <th>DVR</th>
                <th>Canal</th>
                <th>Status</th>
                <th>Local</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filteredCameras.length ? filteredCameras.map((item) => (
                <tr key={item.id} className={getStatusSurfaceClass(item.status, true)}>
                  <td>
                    <strong>{item.name}</strong>
                    <span>{item.resolution || 'Sem resolução'}</span>
                  </td>
                  <td>{item.unit_name}</td>
                  <td>{item.dvr_name || 'Sem DVR'}</td>
                  <td>{item.channel_number}</td>
                  <td><StatusBadge status={item.status} /></td>
                  <td>{item.location || '—'}</td>
                  <td className="actions-cell">
                    <button type="button" className="button primary" onClick={() => openViewerForCamera(item)} title="Abrir visualizador">
                      <Radio size={16} />
                    </button>
                    {allowManage ? (
                      <>
                        <button type="button" className="button ghost" onClick={() => { setEditing(item); setOpen(true) }}>Editar</button>
                        <button type="button" className="button danger" onClick={() => remove(item)}>Excluir</button>
                      </>
                    ) : null}
                  </td>
                </tr>
              )) : (
                <tr>
                  <td colSpan="7">
                    <div className="empty-state">
                      Nenhuma câmera ativa foi encontrada. Sincronize os canais na aba DVRs ou cadastre uma câmera manualmente para começar a validação operacional.
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {allowManage ? (
        <EntityModal
          open={open}
          title={editing ? 'Editar câmera' : 'Nova câmera'}
          fields={fields}
          initialValues={editing || { vendor: 'hikvision', channel_number: 1 }}
          onClose={() => { setOpen(false); setEditing(null) }}
          onSubmit={save}
        />
      ) : null}

      <Modal
        open={viewerOpen}
        title={viewerDvr ? `Visualizador • ${viewerDvr.name}` : 'Visualizador'}
        onClose={closeViewer}
        className={`wide-modal ${getStatusSurfaceClass(viewerCamera?.status || viewerDvr?.status)}`.trim()}
      >
        {viewerError ? <div className="alert-banner error">{viewerError}</div> : null}
        {viewerNotice ? <div className="alert-banner success">{viewerNotice}</div> : null}

        {viewerDvr ? (
          <div className="modal-body">
            <div className="viewer-mode-bar">
              <div className="stack-list compact-list viewer-meta-strip">
                <div className="info-block"><span>DVR</span><strong>{viewerDvr.name}</strong></div>
                <div className="info-block"><span>Canal</span><strong>{viewerSelectedChannel || '—'}</strong></div>
                <div className="info-block"><span>Ocupação</span><strong>{viewerCamera ? viewerCamera.name : 'Canal sem câmera'}</strong></div>
              </div>
              <div className="viewer-toolbar">
                <button type="button" className="button ghost" onClick={() => setViewerChannelsOpen((current) => !current)}>
                  {viewerChannelsOpen ? 'Ocultar canais' : 'Canais'}
                </button>
                <div className="view-toggle viewer-mode-toggle">
                  <button type="button" className={viewerMode === 'live' ? 'active' : ''} onClick={() => toggleViewerMode('live')}>
                    Ao vivo
                  </button>
                  <button type="button" className={viewerMode === 'playback' ? 'active' : ''} onClick={() => toggleViewerMode('playback')}>
                    Reprodução
                  </button>
                </div>
              </div>
            </div>

            {viewerChannelsOpen ? (
              <div className="viewer-channel-grid">
                {viewerChannels.map((channel) => {
                  const channelNumber = Number(channel.id)
                  const hasCamera = Boolean(cameraIndex.get(`${viewerDvr.id}:${channelNumber}`))
                  return (
                    <button
                      key={`${viewerDvr.id}-${channel.id}`}
                      type="button"
                      className={`viewer-channel-pill ${viewerSelectedChannel === channelNumber ? 'selected' : ''} ${hasCamera ? 'connected' : 'empty'} ${getStatusSurfaceClass(cameraIndex.get(`${viewerDvr.id}:${channelNumber}`)?.status)}`}
                      onClick={() => activateViewerChannel(viewerDvr, channelNumber, viewerMode)}
                    >
                      <strong>Canal {channel.id}</strong>
                      <span>{hasCamera ? (cameraIndex.get(`${viewerDvr.id}:${channelNumber}`)?.name || 'Câmera conectada') : 'Sem câmera conectada'}</span>
                    </button>
                  )
                })}
              </div>
            ) : null}

            <section className={`panel ${getStatusSurfaceClass(viewerCamera?.status || viewerDvr?.status)}`.trim()}>
              {viewerMode === 'live' ? (
                <>
                  <div className="panel-header">
                    <div>
                      <span className="eyebrow">Ao vivo</span>
                      <h3>Visualização em tempo real</h3>
                    </div>
                    <StatusBadge status={viewerCamera?.status || 'unknown'} />
                  </div>

                  <div className="media-surface video-surface">
                    {viewerCamera && viewerHlsActive ? (
                      <video
                        ref={videoRef}
                        className="media-video"
                        controls
                        autoPlay
                        muted
                        playsInline
                        src={viewerCamera && nativeHlsSupported ? api.cameraHlsUrl(viewerCamera.id) : undefined}
                      />
                    ) : viewerCamera ? (
                      <div className="preview-placeholder">
                        <PlayCircle size={22} />
                        <span>{viewerLoading ? 'Preparando stream ao vivo...' : 'Inicie o stream do canal selecionado.'}</span>
                      </div>
                    ) : (
                      <div className="empty-channel-state">
                        <Eye size={24} />
                        <strong>Canal não conectado</strong>
                        <span>Este canal não possui câmera cadastrada ou sinal disponível no DVR.</span>
                      </div>
                    )}
                  </div>

                  <div className="stream-box">
                    {viewerCamera
                      ? (viewerHlsActive
                        ? `Canal ${viewerSelectedChannel} em reprodução no player interno.`
                        : viewerCamera.stream_reference || 'Cadastre stream_path ou stream_url para liberar a reprodução ao vivo.')
                      : `Canal ${viewerSelectedChannel || '—'} sem câmera conectada.`}
                  </div>

                  {!inlineHlsSupported ? (
                    <div className="empty-state">
                      Este navegador não conseguiu usar o player HLS interno. Use a aba de reprodução para abrir o playback web do DVR.
                    </div>
                  ) : null}
                </>
              ) : (
                <>
                  <div className="panel-header">
                    <div>
                      <span className="eyebrow">Reprodução</span>
                      <h3>Ocorrências e período passado</h3>
                    </div>
                  </div>

                  {viewerCamera ? (
                    <div className="empty-state">
                      Para consultar ocorrências, reproduzir horários anteriores e exportar trechos, use o playback do próprio DVR. Este caminho é mais estável para este modelo Hikvision do que a busca integrada por firmware.
                    </div>
                  ) : (
                    <div className="empty-channel-state compact">
                      <Eye size={22} />
                      <strong>Canal sem câmera</strong>
                      <span>Selecione um canal ocupado para abrir a reprodução.</span>
                    </div>
                  )}

                  <div className="stream-actions">
                    {viewerWebUrl && viewerCamera ? (
                      <a className="button primary" href={`${viewerWebUrl.replace(/\/$/, '')}/doc/page/playback.asp`} target="_blank" rel="noreferrer">
                        <PlayCircle size={16} />
                        Playback web
                      </a>
                    ) : null}
                    {viewerWebUrl ? (
                      <a className="button ghost" href={viewerWebUrl} target="_blank" rel="noreferrer">
                        Abrir interface
                      </a>
                    ) : null}
                  </div>

                  <div className="stream-box">
                    {viewerWebUrl && viewerCamera
                      ? `${viewerWebUrl.replace(/\/$/, '')}/doc/page/playback.asp`
                      : 'Selecione um canal ocupado para liberar a reprodução pela interface do DVR.'}
                  </div>
                </>
              )}
            </section>
          </div>
        ) : null}
      </Modal>
    </section>
  )
}
