import { useEffect, useState } from 'react'

import Sidebar from './components/Sidebar'
import { useRealtime } from './hooks/useRealtime'
import BackupsPage from './pages/BackupsPage'
import CamerasPage from './pages/CamerasPage'
import CloudAccountsPage from './pages/CloudAccountsPage'
import DashboardPage from './pages/DashboardPage'
import DvrsPage from './pages/DvrsPage'
import EventsPage from './pages/EventsPage'
import LoginPage from './pages/LoginPage'
import NetworkAssetsPage from './pages/NetworkAssetsPage'
import ReportsPage from './pages/ReportsPage'
import UnitsPage from './pages/UnitsPage'
import UsersPage from './pages/UsersPage'
import { clearStoredToken, getStoredToken, isAdmin, storeToken } from './utils/auth'
import { api, setAuthToken } from './utils/api'

export default function App() {
  const [page, setPage] = useState('dashboard')
  const [refreshToken, setRefreshToken] = useState(0)
  const [feed, setFeed] = useState([])
  const [currentUser, setCurrentUser] = useState(null)
  const [booting, setBooting] = useState(true)
  const [loggingIn, setLoggingIn] = useState(false)

  useEffect(() => {
    const bootstrap = async () => {
      const token = getStoredToken()
      if (!token) {
        setBooting(false)
        return
      }

      try {
        setAuthToken(token)
        const user = await api.getMe()
        setCurrentUser(user)
      } catch {
        clearStoredToken()
        setAuthToken(null)
      } finally {
        setBooting(false)
      }
    }

    bootstrap()
  }, [])

  const { connected } = useRealtime(getStoredToken(), (message) => {
    setFeed((current) => [message, ...current].slice(0, 8))
    if (['health_check_complete', 'backup_completed', 'event_created'].includes(message.type)) {
      setRefreshToken((value) => value + 1)
    }
  })

  useEffect(() => {
    document.title = `SPYGYM • ${page}`
  }, [page])

  const handleLogin = async (credentials) => {
    setLoggingIn(true)
    try {
      const session = await api.login(credentials)
      storeToken(session.token)
      setAuthToken(session.token)
      setCurrentUser(session.user)
      setRefreshToken((value) => value + 1)
      setPage('dashboard')
    } finally {
      setLoggingIn(false)
    }
  }

  const handleLogout = async () => {
    try {
      await api.logout()
    } catch {
      // Ignora falhas de rede no logout e limpa a sessão local mesmo assim.
    }
    clearStoredToken()
    setAuthToken(null)
    setCurrentUser(null)
    setFeed([])
  }

  if (booting) {
    return <LoginPage onLogin={handleLogin} loading={loggingIn} booting />
  }

  if (!currentUser) {
    return <LoginPage onLogin={handleLogin} loading={loggingIn} />
  }

  return (
    <div className="app-shell">
      <Sidebar page={page} setPage={setPage} connected={connected} currentUser={currentUser} />

      <main className="content-shell">
        {page === 'dashboard' && <DashboardPage refreshToken={refreshToken} feed={feed} connected={connected} currentUser={currentUser} onLogout={handleLogout} />}
        {page === 'units' && <UnitsPage refreshToken={refreshToken} connected={connected} currentUser={currentUser} onLogout={handleLogout} />}
        {page === 'dvrs' && <DvrsPage refreshToken={refreshToken} connected={connected} currentUser={currentUser} onLogout={handleLogout} />}
        {page === 'cloud-accounts' && <CloudAccountsPage refreshToken={refreshToken} connected={connected} currentUser={currentUser} onLogout={handleLogout} />}
        {page === 'network-assets' && <NetworkAssetsPage refreshToken={refreshToken} connected={connected} currentUser={currentUser} onLogout={handleLogout} />}
        {page === 'cameras' && <CamerasPage refreshToken={refreshToken} connected={connected} currentUser={currentUser} onLogout={handleLogout} />}
        {page === 'reports' && <ReportsPage connected={connected} currentUser={currentUser} onLogout={handleLogout} />}
        {page === 'events' && <EventsPage refreshToken={refreshToken} connected={connected} currentUser={currentUser} onLogout={handleLogout} />}
        {page === 'backups' && <BackupsPage refreshToken={refreshToken} connected={connected} currentUser={currentUser} onLogout={handleLogout} />}
        {page === 'users' && isAdmin(currentUser) && <UsersPage refreshToken={refreshToken} connected={connected} currentUser={currentUser} onLogout={handleLogout} />}
      </main>
    </div>
  )
}
