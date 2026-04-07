const TOKEN_KEY = 'spygym_auth_token'

export function getStoredToken() {
  try {
    return window.localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function storeToken(token) {
  try {
    window.localStorage.setItem(TOKEN_KEY, token)
  } catch {
    return null
  }
  return token
}

export function clearStoredToken() {
  try {
    window.localStorage.removeItem(TOKEN_KEY)
  } catch {
    return null
  }
  return null
}

export function isAdmin(user) {
  return user?.role === 'admin'
}

export function canManage(user) {
  return ['admin', 'operator'].includes(user?.role)
}

export function roleLabel(role) {
  if (role === 'admin') return 'Administrador'
  if (role === 'operator') return 'Operador'
  return 'Visualizador'
}
