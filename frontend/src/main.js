import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import * as Icons from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'
import '@fontsource/battambang/400.css'
import '@fontsource/battambang/700.css'
import '@fontsource/moul/400.css'
import './styles.css'

import App from './App.vue'
import router from './router'
import { i18n } from './i18n'

const app = createApp(App)
for (const [name, comp] of Object.entries(Icons)) app.component(name, comp)
app.use(createPinia()).use(router).use(i18n).use(ElementPlus)
app.mount('#app')
