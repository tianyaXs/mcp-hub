<template>
  <div class="theme-switcher">
    <el-tooltip
      v-for="theme in themes"
      :key="theme.type"
      :content="theme.label"
      placement="bottom"
    >
      <div
        class="theme-option"
        :class="{ active: currentTheme === theme.type }"
        @click="switchTheme(theme.type)"
      >
        <el-icon>
          <component :is="theme.icon" />
        </el-icon>
      </div>
    </el-tooltip>
  </div>
</template>

<script setup lang="ts">
import { Sunny, Moon, Sunset } from '@element-plus/icons-vue'
import { currentTheme, type ThemeType, applyTheme } from '../utils/theme'

const themes = [
  {
    type: 'light' as ThemeType,
    label: '白天模式',
    icon: Sunny
  },
  {
    type: 'dark' as ThemeType,
    label: '夜晚模式',
    icon: Moon
  },
  {
    type: 'sunset' as ThemeType,
    label: '黄昏模式',
    icon: Sunset
  }
]

const switchTheme = (theme: ThemeType) => {
  applyTheme(theme)
}
</script>

<style scoped>
.theme-switcher {
  display: flex;
  gap: 8px;
  padding: 4px;
  background-color: var(--mcp-bgSecondary);
  border-radius: 8px;
}

.theme-option {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  cursor: pointer;
  color: var(--mcp-textSecondary);
  transition: all 0.3s ease;
}

.theme-option:hover {
  background-color: var(--mcp-bgTertiary);
  color: var(--mcp-textPrimary);
}

.theme-option.active {
  background-color: var(--mcp-primary);
  color: var(--mcp-textPrimary);
}
</style> 
