import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err?.response?.status
    const detail = err?.response?.data?.detail
    const msg = detail
      ? (Array.isArray(detail) ? detail.map(d => d.msg).join(', ') : String(detail))
      : err?.message || 'Erro desconhecido'
    console.error('[API Error]', err?.config?.url, status, msg, err?.response?.data)
    return Promise.reject(new Error(msg))
  }
)

// ── Units ─────────────────────────────────────────────────────
export const getUnits   = ()         => api.get('/units')
export const createUnit = (data)     => api.post('/units', data)
export const updateUnit = (id, data) => api.put(`/units/${id}`, data)
export const deleteUnit = (id)       => api.delete(`/units/${id}`)

// ── DVRs ──────────────────────────────────────────────────────
export const getDVRs     = (unitId)   => api.get('/dvrs', { params: unitId ? { unit_id: unitId } : {} })
export const getDVR      = (id)       => api.get(`/dvrs/${id}`)
export const createDVR   = (data)     => api.post('/dvrs', data)
export const updateDVR   = (id, data) => api.put(`/dvrs/${id}`, data)
export const deleteDVR   = (id)       => api.delete(`/dvrs/${id}`)
export const checkDVR    = (id)       => api.post(`/dvrs/${id}/check`)
export const syncCameras = (id)       => api.post(`/dvrs/${id}/sync-cameras`)

// ── Cameras ───────────────────────────────────────────────────
export const getCameras   = (unitId, dvrId) => api.get('/cameras', {
  params: { ...(unitId && { unit_id: unitId }), ...(dvrId && { dvr_id: dvrId }) }
})
export const createCamera = (data)     => api.post('/cameras', data)
export const updateCamera = (id, data) => api.put(`/cameras/${id}`, data)
export const deleteCamera = (id)       => api.delete(`/cameras/${id}`)

// ── Cloud Accounts ────────────────────────────────────────────
export const getCloudAccounts     = (vendor)   => api.get('/cloud-accounts', { params: vendor ? { vendor } : {} })
export const getCloudAccount      = (id)       => api.get(`/cloud-accounts/${id}`)
export const createCloudAccount   = (data)     => api.post('/cloud-accounts', data)
export const updateCloudAccount   = (id, data) => api.put(`/cloud-accounts/${id}`, data)
export const deleteCloudAccount   = (id)       => api.delete(`/cloud-accounts/${id}`)
export const getCloudAccountDVRs  = (id)       => api.get(`/cloud-accounts/${id}/dvrs`)
export const revealCloudPassword  = (id)       => api.get(`/cloud-accounts/${id}/reveal-password`)

// ── Streaming ─────────────────────────────────────────────────
export const startStream     = (cameraId) => api.post(`/streaming/${cameraId}/start`)
export const stopStream      = (cameraId) => api.post(`/streaming/${cameraId}/stop`)
export const getHlsUrl       = (cameraId) => `/api/streaming/${cameraId}/hls`
export const getVlcLink      = (cameraId) => api.get(`/streaming/${cameraId}/vlc-link`)
export const getStreamStatus = ()         => api.get('/streaming/status')

// ── DVR Remote ────────────────────────────────────────────────
export const getDVRWebUrl     = (id)          => api.get(`/dvr-remote/${id}/web-url`)
export const getDVRChannels   = (id)          => api.get(`/dvr-remote/${id}/channels`)
export const getDVRRecordings = (id, params)  => api.get(`/dvr-remote/${id}/recordings`, { params })
export const rebootDVR        = (id)          => api.post(`/dvr-remote/${id}/reboot`)
export const getDVRProxyUrl   = (id, path='/') => `/api/dvr-remote/${id}/proxy?path=${encodeURIComponent(path)}`

// ── Audit Logs ────────────────────────────────────────────────
export const getAuditLogs      = (params)    => api.get('/audit', { params })
export const getAuditFiles     = ()          => api.get('/audit/files')
export const downloadAuditFile = (filename)  => `/api/audit/files/${filename}`

// ── Dashboard ─────────────────────────────────────────────────
export const getDashboard = () => api.get('/dashboard/overview')

// ── Events ────────────────────────────────────────────────────
export const getEvents = (limit = 100) => api.get('/events', { params: { limit } })

// ── Backups ───────────────────────────────────────────────────
export const getBackups = () => api.get('/backups')
export const runBackup  = () => api.post('/backups/run')

// ── Auth ──────────────────────────────────────────────────────
export const login  = (data) => api.post('/auth/login', data)
export const logout = ()     => api.post('/auth/logout')
export const getMe  = ()     => api.get('/auth/me')

// ── Users ─────────────────────────────────────────────────────
export const getUsers   = ()         => api.get('/users')
export const createUser = (data)     => api.post('/users', data)
export const updateUser = (id, data) => api.put(`/users/${id}`, data)
export const deleteUser = (id)       => api.delete(`/users/${id}`)

export default api
