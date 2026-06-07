import * as SecureStore from 'expo-secure-store'

const DEFAULT_BASE = 'http://10.0.2.2:5000'
export const API_BASE = process.env.EXPO_PUBLIC_API_BASE || DEFAULT_BASE

let authToken = ''

export async function restoreToken() {
  authToken = (await SecureStore.getItemAsync('dispatch_token')) || ''
  return authToken
}

export async function setToken(token) {
  authToken = token || ''
  if (authToken) {
    await SecureStore.setItemAsync('dispatch_token', authToken)
  } else {
    await SecureStore.deleteItemAsync('dispatch_token')
  }
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
