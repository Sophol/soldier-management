import { ref } from 'vue'

/** Bumped after the logo is uploaded or removed, so every <BrandLogo> reloads it. */
export const logoVersion = ref(Date.now())
export const refreshLogo = () => { logoVersion.value = Date.now() }
