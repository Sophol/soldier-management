// Light / dark mode: Element Plus's dark theme (class "dark" on <html>) plus the app's own colours (styles.css).
// The choice is kept in this browser; without one, the system's setting is followed.
import { computed, ref, watch } from 'vue'

const KEY = 'theme'

function initial() {
  try {
    const saved = localStorage.getItem(KEY)
    if (saved === 'dark' || saved === 'light') return saved
  } catch { /* storage blocked: follow the system */ }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function apply(value) {
  document.documentElement.classList.toggle('dark', value === 'dark')
  document.documentElement.style.colorScheme = value
}

export const theme = ref(initial())
export const isDark = computed(() => theme.value === 'dark')
apply(theme.value)

watch(theme, (value) => {
  apply(value)
  try { localStorage.setItem(KEY, value) } catch { /* only this visit */ }
})

export function toggleTheme() {
  theme.value = isDark.value ? 'light' : 'dark'
}
