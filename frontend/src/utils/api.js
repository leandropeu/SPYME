const RAW_API = import.meta.env.VITE_API_URL || '/api'

export const API_BASE = RAW_API
export const ROOT_API = RAW_API.replace(/\/api\/?$/, '')
let authToken = null

export function setAuthToken(token) {
  authToken = token || null
}

async function request(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  }

  if (authToken && !options.skipAuth) {
    headers.Authorization = `Bearer ${authToken}`
  }

  const response = await fetch(`${API_BASE}${path}`, {
    headers,
    ...options,
  })

  if (!response.ok) {
    let detail = 'Falha na comunicação com o backend.'
    try {
      const data = await response.json()
      detail = data.detail || detail
    } catch {
      detail = response.statusText || detail
    }
    throw new Error(detail)
  }

  if (response.status === 204) {
    return null
  }
  return response.json()
}

export const api = {
  health: () => request('/health'),
  login: (payload) => request('/auth/login', { method: 'POST', body: JSON.stringify(payload), skipAuth: true }),
  logout: () => request('/auth/logout', { method: 'POST' }),
  getMe: () => request('/auth/me'),
  listUsers: () => request('/users'),
  createUser: (payload) => request('/users', { method: 'POST', body: JSON.stringify(payload) }),
  updateUser: (id, payload) => request(`/users/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteUser: (id) => request(`/users/${id}`, { method: 'DELETE' }),
  getOverview: () => request('/dashboard/overview'),
  listUnits: () => request('/units'),
  createUnit: (payload) => request('/units', { method: 'POST', body: JSON.stringify(payload) }),
  updateUnit: (id, payload) => request(`/units/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteUnit: (id) => request(`/units/${id}`, { method: 'DELETE' }),
  listNetworkAssets: ({ unitId, assetType } = {}) => {
    const params = new URLSearchParams()
    if (unitId) params.set('unit_id', unitId)
    if (assetType) params.set('asset_type', assetType)
    const qs = params.toString()
    return request(`/network-assets${qs ? `?${qs}` : ''}`)
  },
  createNetworkAsset: (payload) => request('/network-assets', { method: 'POST', body: JSON.stringify(payload) }),
  updateNetworkAsset: (id, payload) => request(`/network-assets/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteNetworkAsset: (id) => request(`/network-assets/${id}`, { method: 'DELETE' }),

  listDvrs: (unitId) => request(unitId ? `/dvrs?unit_id=${unitId}` : '/dvrs'),
  createDvr: (payload) => request('/dvrs', { method: 'POST', body: JSON.stringify(payload) }),
  updateDvr: (id, payload) => request(`/dvrs/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteDvr: (id) => request(`/dvrs/${id}`, { method: 'DELETE' }),
  checkDvr: (id) => request(`/dvrs/${id}/check`, { method: 'POST' }),
  syncDvrCameras: (id) => request(`/dvrs/${id}/sync-cameras`, { method: 'POST' }),
  listCloudAccounts: (vendor) => request(vendor ? `/cloud-accounts?vendor=${encodeURIComponent(vendor)}` : '/cloud-accounts'),
  createCloudAccount: (payload) => request('/cloud-accounts', { method: 'POST', body: JSON.stringify(payload) }),
  updateCloudAccount: (id, payload) => request(`/cloud-accounts/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteCloudAccount: (id) => request(`/cloud-accounts/${id}`, { method: 'DELETE' }),
  revealCloudAccountPassword: (id) => request(`/cloud-accounts/${id}/reveal-password`),
  listCloudAccountDvrs: (id) => request(`/cloud-accounts/${id}/dvrs`),

  listCameras: ({ unitId, dvrId } = {}) => {
    const params = new URLSearchParams()
    if (unitId) params.set('unit_id', unitId)
    if (dvrId) params.set('dvr_id', dvrId)
    const qs = params.toString()
    return request(`/cameras${qs ? `?${qs}` : ''}`)
  },
  createCamera: (payload) => request('/cameras', { method: 'POST', body: JSON.stringify(payload) }),
  updateCamera: (id, payload) => request(`/cameras/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteCamera: (id) => request(`/cameras/${id}`, { method: 'DELETE' }),
  cameraSnapshotUrl: (id) => `${ROOT_API}/api/cameras/${id}/snapshot${authToken ? `?token=${encodeURIComponent(authToken)}` : ''}`,
  startStream: (cameraId) => request(`/streaming/${cameraId}/start`, { method: 'POST' }),
  stopStream: (cameraId) => request(`/streaming/${cameraId}/stop`, { method: 'POST' }),
  getVlcLink: (cameraId) => request(`/streaming/${cameraId}/vlc-link`),
  getStreamStatus: () => request('/streaming/status'),
  cameraHlsUrl: (cameraId) => `${ROOT_API}/api/streaming/${cameraId}/hls${authToken ? `?token=${encodeURIComponent(authToken)}` : ''}`,

  getDvrWebUrl: (dvrId) => request(`/dvr-remote/${dvrId}/web-url`),
  getDvrChannels: (dvrId) => request(`/dvr-remote/${dvrId}/channels`),
  getDvrRecordings: (dvrId, { channel, start, end } = {}) => {
    const params = new URLSearchParams()
    if (channel) params.set('channel', channel)
    if (start) params.set('start', start)
    if (end) params.set('end', end)
    const qs = params.toString()
    return request(`/dvr-remote/${dvrId}/recordings${qs ? `?${qs}` : ''}`)
  },
  rebootDvr: (dvrId) => request(`/dvr-remote/${dvrId}/reboot`, { method: 'POST' }),
  dvrProxyUrl: (dvrId, path = '/') => {
    const params = new URLSearchParams()
    params.set('path', path)
    if (authToken) params.set('token', authToken)
    return `${ROOT_API}/api/dvr-remote/${dvrId}/proxy?${params.toString()}`
  },
  dvrRecordingProxyUrl: (dvrId, playbackUrl, download = false) => {
    const params = new URLSearchParams()
    params.set('playback_url', playbackUrl)
    if (download) params.set('download', 'true')
    if (authToken) params.set('token', authToken)
    return `${ROOT_API}/api/dvr-remote/${dvrId}/recordings/proxy?${params.toString()}`
  },

  listEvents: (limit = 100) => request(`/events?limit=${limit}`),
  listBackups: () => request('/backups'),
  runBackup: () => request('/backups/run', { method: 'POST' }),
  runMonitor: () => request('/monitor/run', { method: 'POST' }),
}
