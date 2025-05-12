import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import { initTheme } from './utils/theme' // 导入主题初始化函数

// 初始化主题
initTheme()

// 创建Vue应用实例
const app = createApp(App)

// 注册所有Element Plus图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 使用Pinia进行状态管理
app.use(createPinia())

// 使用Element Plus组件库
app.use(ElementPlus)

// 使用Vue Router
app.use(router)

// 挂载应用
app.mount('#app') 
