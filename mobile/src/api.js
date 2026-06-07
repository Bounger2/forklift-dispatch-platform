import * as SecureStore from 'expo-secure-store'
import { Platform } from 'react-native'

const TOKEN_KEY = 'dispatch_token'
const DEFAULT_BASE = Platform.OS === 'web' ? 'http://127.0.0.1:5000' : 'http://10.0.2.2:5000'
export const API_BASE = process.env.EXPO_PUBLIC_API_BASE || DEFAULT_BASE

let authToken = ''

async function getStoredToken() {
  if (Platform.OS === 'web') {
    return window.localStorage.getItem(TOKEN_KEY) || ''
  }
  return (await SecureStore.getItemAsync(TOKEN_KEY)) || ''
}

async function storeToken(token) {
  if (Platform.OS === 'web') {
    if (token) window.localStorage.setItem(TOKEN_KEY, token)
    else window.localStorage.removeItem(TOKEN_KEY)
    return
  }

  if (token) {
    await SecureStore.setItemAsync(TOKEN_KEY, token)
  } else {
    await SecureStore.deleteItemAsync(TOKEN_KEY)
  }
}

export async function restoreToken() {
  authToken = await getStoredToken()
  return authToken
}

export async function setToken(token) {
  authToken = token || ''
  await storeToken(authToken)
}

export async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) }
  let body = options.body
  if (authToken) headers.Authorization = `Bearer ${authToken}`
  if (body && typeof body === 'object') {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(body)
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers, body })
  const payload = await res.json().catch(() => ({ message: res.statusText }))
  if (!res.ok) {
    throw new Error(payload.message || '请求失败')
  }
  return payload.data
}

export const api = {
  login: (body) => request('/api/auth/login', { method: 'POST', body }),
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body }),
  patch: (path, body) => request(path, { method: 'PATCH', body }),
  put: (path, body) => request(path, { method: 'PUT', body }),
  del: (path) => request(path, { method: 'DELETE' }),
}
