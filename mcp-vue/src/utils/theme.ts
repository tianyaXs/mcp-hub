import { ref } from 'vue'

export type ThemeType = 'light' | 'dark' | 'sunset'

export interface ThemeColors {
  // 背景色
  bgPrimary: string
  bgSecondary: string
  bgTertiary: string
  
  // 文字颜色
  textPrimary: string
  textSecondary: string
  
  // 边框颜色
  borderPrimary: string
  borderSecondary: string
  
  // 主题色
  primary: string
  primaryHover: string
  
  // 状态颜色
  success: string
  warning: string
  danger: string
  info: string
}

export const themes: Record<ThemeType, ThemeColors> = {
  light: {
    bgPrimary: '#FFFFFF',
    bgSecondary: '#F5F7FA',
    bgTertiary: '#E4E7ED',
    textPrimary: '#303133',
    textSecondary: '#606266',
    borderPrimary: '#DCDFE6',
    borderSecondary: '#E4E7ED',
    primary: '#409EFF',
    primaryHover: '#337ECC',
    success: '#67C23A',
    warning: '#E6A23C',
    danger: '#F56C6C',
    info: '#909399'
  },
  dark: {
    bgPrimary: '#121212',
    bgSecondary: '#1E1E1E',
    bgTertiary: '#2C2C2C',
    textPrimary: '#FFFFFF',
    textSecondary: '#909399',
    borderPrimary: '#2C2C2C',
    borderSecondary: '#3C3C3C',
    primary: '#409EFF',
    primaryHover: '#337ECC',
    success: '#67C23A',
    warning: '#E6A23C',
    danger: '#F56C6C',
    info: '#909399'
  },
  sunset: {
    bgPrimary: '#1A1A1A',
    bgSecondary: '#2C2C2C',
    bgTertiary: '#3C3C3C',
    textPrimary: '#FFFFFF',
    textSecondary: '#888888',
    borderPrimary: '#2C2C2C',
    borderSecondary: '#3C3C3C',
    primary: '#D32F2F',
    primaryHover: '#B71C1C',
    success: '#4CAF50',
    warning: '#FFA726',
    danger: '#D32F2F',
    info: '#888888'
  }
}

// 当前主题
export const currentTheme = ref<ThemeType>('sunset')

// CSS 变量前缀
const cssPrefix = '--mcp'

// 生成 CSS 变量名
const getCssVarName = (name: string) => `${cssPrefix}-${name}`

// 应用主题
export function applyTheme(theme: ThemeType) {
  currentTheme.value = theme
  const colors = themes[theme]
  const root = document.documentElement
  
  // 设置所有颜色变量
  Object.entries(colors).forEach(([key, value]) => {
    root.style.setProperty(getCssVarName(key), value)
  })
  
  // 保存到本地存储
  localStorage.setItem('mcp-theme', theme)
}

// 初始化主题
export function initTheme() {
  const savedTheme = localStorage.getItem('mcp-theme') as ThemeType
  applyTheme(savedTheme || 'sunset')
} 
