import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({ baseURL: '/api/v1', timeout: 60000 })

const tokens = {
  get access() { return localStorage.getItem('access_token') },
  get refresh() { return localStorage.getItem('refresh_token') },
  set(access, refresh) {
    localStorage.setItem('access_token', access)
    if (refresh) localStorage.setItem('refresh_token', refresh)
  },
  clear() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  },
}

http.interceptors.request.use((config) => {
  if (tokens.access) config.headers.Authorization = `Bearer ${tokens.access}`
  return config
})

let refreshing = null

http.interceptors.response.use(
  (res) => res,
  async (error) => {
    const { config, response } = error
    if (response?.status === 401 && tokens.refresh && !config._retry && !config.url.includes('/auth/')) {
      config._retry = true
      try {
        refreshing = refreshing || axios.post('/api/v1/auth/refresh', { refresh_token: tokens.refresh })
        const { data } = await refreshing
        tokens.set(data.access_token)
        config.headers.Authorization = `Bearer ${data.access_token}`
        return http(config)
      } catch {
        tokens.clear()
        window.location.href = '/login'
      } finally {
        refreshing = null
      }
    }
    if (response?.status === 401 && !config.url.includes('/auth/login')) {
      tokens.clear()
      if (window.location.pathname !== '/login') window.location.href = '/login'
    }
    if (!config.silent) ElMessage.error(errorMessage(error))
    return Promise.reject(error)
  },
)

export function errorMessage(error) {
  const detail = error.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((d) => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`).join('\n')
  }
  if (detail instanceof Blob) return 'មានបញ្ហា'
  return detail || error.message || 'មានបញ្ហា'
}

/** Download a protected file (Bearer token) and save it with its server-side name. */
export async function download(url, params = {}, fallbackName = 'download') {
  const res = await http.get(url, { params, responseType: 'blob' })
  const cd = res.headers['content-disposition'] || ''
  const m = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(cd)
  const name = m ? decodeURIComponent(m[1]) : fallbackName
  const href = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = href
  a.download = name
  a.click()
  URL.revokeObjectURL(href)
}

/** Fetch a protected file as an object URL (for <img> / preview). */
export async function blobUrl(url) {
  const res = await http.get(url, { responseType: 'blob', silent: true })
  return URL.createObjectURL(res.data)
}

export { tokens }
export default http
