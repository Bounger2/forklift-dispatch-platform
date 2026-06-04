const API_BASE = import.meta.env.VITE_API_BASE || ''

let token = localStorage.getItem('dispatch_token') || ''

export function setToken(value) {
  token = value || ''
  if (token) {
    localStorage.setItem('dispatch_token', token)
  } else {
    localStorage.removeItem('dispatch_token')
  }
}

export function getToken() {
  return token
}

export async function request(path, options = {}) {
  const headers = {
    ...(options.headers || {}),
  }
  if (token) headers.Authorization = `Bearer ${token}`
  let body = options.body
  if (body && typeof body === 'object' && !(body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(body)
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    body,
  })
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
  put: (path, body) => request(path, { method: 'PUT', body }),
  patch: (path, body) => request(path, { method: 'PATCH', body }),
  del: (path) => request(path, { method: 'DELETE' }),
}
