import { onBeforeUnmount, onMounted, ref } from 'vue'

// A list table's max height: the window less the top bar, page title and pagination, so its rows scroll
// inside the table while the column headers stay in place (never shorter than `min`).
export function useTableHeight(offset = 250, min = 400) {
  const height = ref(min)
  const update = () => { height.value = Math.max(min, window.innerHeight - offset) }
  onMounted(() => {
    update()
    window.addEventListener('resize', update)
  })
  onBeforeUnmount(() => window.removeEventListener('resize', update))
  return height
}
