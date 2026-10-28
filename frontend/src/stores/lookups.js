import { defineStore } from 'pinia'
import http from '@/api/http'

/** All dropdown lists (ranks, positions, lookups...) and the unit tree, cached. */
export const useLookups = defineStore('lookups', {
  state: () => ({ data: {}, unitTree: [], loaded: false, users: null }),
  getters: {
    list: (s) => (key) => s.data[key] || [],
    unitMap: (s) => {
      const map = {}
      const walk = (nodes) => nodes.forEach((n) => { map[n.id] = n; walk(n.children || []) })
      walk(s.unitTree)
      return map
    },
  },
  actions: {
    async load(force = false) {
      if (this.loaded && !force) return
      const [lk, tree] = await Promise.all([http.get('/lookups/all'), http.get('/units/tree')])
      this.data = lk.data
      this.unitTree = tree.data
      this.loaded = true
    },
    /** Users for the "entered by" (អ្នកបញ្ចូល) filters, fetched once. */
    async loadUsers() {
      if (!this.users) this.users = (await http.get('/users/options')).data
      return this.users
    },
    refresh() {
      return this.load(true)
    },
    name(key, id) {
      if (id == null) return ''
      return (this.data[key] || []).find((x) => x.id === id)?.name_kh || ''
    },
  },
})
