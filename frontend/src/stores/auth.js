import { defineStore } from 'pinia'
import http, { tokens } from '@/api/http'

export const useAuth = defineStore('auth', {
  state: () => ({ user: null, loaded: false }),
  getters: {
    isLoggedIn: (s) => !!s.user,
    perms: (s) => new Set(s.user?.permissions || []),
  },
  actions: {
    async login(username, password) {
      const { data } = await http.post('/auth/login', { username, password })
      tokens.set(data.access_token, data.refresh_token)
      this.user = data.user
      this.loaded = true
    },
    async fetchMe() {
      if (!tokens.access) {
        this.loaded = true
        return
      }
      try {
        const { data } = await http.get('/auth/me', { silent: true })
        this.user = data
      } catch {
        this.user = null
      }
      this.loaded = true
    },
    logout() {
      tokens.clear()
      this.user = null
      window.location.href = '/login'
    },
    can(perm) {
      if (!perm) return true
      if (this.user?.is_super) return true
      const list = Array.isArray(perm) ? perm : [perm]
      return list.some((p) => this.perms.has(p))
    },
  },
})
