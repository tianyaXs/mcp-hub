<template>
  <div class="home-container">
    <el-container class="main-layout">
      <!-- 左侧边栏 -->
      <el-aside width="250px" class="left-sidebar">
        <div class="sidebar-top">
          <div class="logo-area">
            <h2>
              <el-icon class="logo-icon"><Operation /></el-icon>
              MCP-Hub
            </h2>
          </div>
          <div class="sidebar-description">
            Manage and configure your MCP servers
          </div>
        </div>
        
        <div class="sidebar-bottom">
          <!-- 服务统计 -->
          <div class="stats-section">
            <div class="stat-card">
              <div class="stat-label">Total Servers</div>
              <div class="stat-value">{{ serviceStore.serviceStats.total }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">SSE Servers</div>
              <div class="stat-value">{{ serviceStore.serviceStats.sseServices }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">Total Tools</div>
              <div class="stat-value">{{ serviceStore.toolStats.total }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">SSE Tools</div>
              <div class="stat-value">{{ serviceStore.toolStats.sseTools }}</div>
            </div>
          </div>
          
          <!-- 操作按钮 -->
          <div class="sidebar-actions">
            <el-button 
              type="primary" 
              class="action-button" 
              @click="showServiceDialog = true"
            >
              <el-icon><Plus /></el-icon>
              Add Server
            </el-button>
            
            <el-button 
              type="default" 
              class="action-button" 
              @click="showConfigDialog = true"
            >
              <el-icon><Setting /></el-icon>
              Config Manager
            </el-button>
          </div>
          
          <!-- 外部链接 -->
          <div class="external-links">
            <a href="https://github.com/yourusername/mcp-client" target="_blank" class="link-item">
              <el-icon><Link /></el-icon> GitHub Repo
            </a>
            <a href="https://docs.example.com/mcp-client" target="_blank" class="link-item">
              <el-icon><Document /></el-icon> Documentation
            </a>
          </div>

          <!-- 主题切换器 -->
          <div class="theme-switcher-container">
            <ThemeSwitcher />
          </div>
        </div>
      </el-aside>
      
      <!-- 中间内容区域 -->
      <el-container class="center-content">
        <el-header class="main-header">
          <div class="header-title">Server List</div>
          <div class="header-actions">
            <el-button type="primary" @click="showServiceDialog = true">
              <el-icon><Plus /></el-icon> Add Server
            </el-button>
          </div>
        </el-header>
        
        <el-main class="main-content">
          <!-- 服务状态区域 -->
          <service-status />
          
          <!-- 服务为空时的提示 -->
          <div v-if="serviceCount === 0" class="empty-servers">
            <el-empty description="No servers configured. Click 'Add Server' to get started." />
          </div>
        </el-main>
      </el-container>
      
      <!-- 右侧聊天区域 -->
      <el-aside :width="'33.33vw'" class="chat-sidebar">
        <chat-window />
      </el-aside>
    </el-container>
    
    <!-- 服务添加弹窗 -->
    <el-dialog
      v-model="showServiceDialog"
      title="Add New Server"
      width="500px"
      :close-on-click-modal="false"
      class="mcp-theme-dialog"
    >
      <service-register @close="showServiceDialog = false" mode="dialog" />
    </el-dialog>
    
    <!-- 配置管理弹窗 -->
    <el-dialog
      v-model="showConfigDialog"
      title="MCP Configuration Manager"
      width="650px"
      :close-on-click-modal="false"
      class="mcp-theme-dialog"
    >
      <config-manager @close="showConfigDialog = false" mode="dialog" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import ChatWindow from '../components/ChatWindow.vue'
import ServiceStatus from '../components/ServiceStatus.vue'
import ServiceRegister from '../components/ServiceRegister.vue'
import ConfigManager from '../components/ConfigManager.vue'
import ThemeSwitcher from '../components/ThemeSwitcher.vue'
import { useServiceStore } from '../stores/services'
import { Operation, Plus, Setting, Link, Document } from '@element-plus/icons-vue'

// 初始化
const serviceStore = useServiceStore()
const showServiceDialog = ref(false)
const showConfigDialog = ref(false)

// 服务计数
const serviceCount = computed(() => serviceStore.serviceStats.total)

// 组件挂载时获取数据
onMounted(async () => {
  await serviceStore.fetchHealthStatus()
})
</script>

<style scoped>
.home-container {
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background-color: var(--mcp-bgPrimary);
}

.main-layout {
  height: 100%;
}

/* 左侧边栏样式 */
.left-sidebar {
  background-color: var(--mcp-bgPrimary);
  border-right: 1px solid var(--mcp-borderPrimary);
  padding: 20px;
  display: flex;
  flex-direction: column;
  height: 100%;
  box-sizing: border-box;
  overflow: hidden;
}

.sidebar-top {
  flex-shrink: 0;
}

.sidebar-bottom {
  flex: 1;
  display: flex;
  flex-direction: column;
  width: 100%;
  box-sizing: border-box;
  padding: 0;
  gap: 16px;
}

.logo-area {
  margin-bottom: 16px;
}

.logo-area h2 {
  display: flex;
  align-items: center;
  font-size: 1.5rem;
  margin: 0;
  color: var(--mcp-textPrimary);
}

.logo-icon {
  margin-right: 8px;
  font-size: 1.5rem;
  color: var(--mcp-primary);
}

.sidebar-description {
  color: var(--mcp-textSecondary);
  margin-bottom: 24px;
  font-size: 0.9rem;
}

/* 统计卡片区域样式 */
.stats-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 24px;
  padding: 0;
  width: 100%;
  box-sizing: border-box;
}

.stat-card {
  width: 100%;
  background-color: var(--mcp-bgSecondary);
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  border: 1px solid var(--mcp-borderSecondary);
  transition: all 0.3s ease;
  box-sizing: border-box;
  margin: 0;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
  border-color: var(--mcp-primary);
}

.stat-label {
  font-size: 12px;
  color: var(--mcp-textSecondary);
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--mcp-textPrimary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 操作按钮样式 */
.sidebar-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

:deep(.action-button) {
  width: 100% !important;
  margin: 0 !important;
  padding: 0 12px !important;
  background-color: var(--mcp-bgSecondary) !important;
  border-color: var(--mcp-borderSecondary) !important;
  color: var(--mcp-textPrimary) !important;
}

:deep(.action-button:hover) {
  background-color: var(--mcp-primary) !important;
  border-color: var(--mcp-primary) !important;
}

:deep(.action-button.el-button--primary) {
  background-color: var(--mcp-primary) !important;
  border-color: var(--mcp-primary) !important;
}

:deep(.action-button.el-button--primary:hover) {
  background-color: var(--mcp-primaryHover) !important;
  border-color: var(--mcp-primaryHover) !important;
}

/* 外部链接样式 */
.external-links {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  background-color: var(--mcp-bgSecondary);
  border-radius: 8px;
  margin-bottom: 0;
}

.link-item {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--mcp-textPrimary);
  text-decoration: none;
  font-size: 14px;
  padding: 8px;
  border-radius: 4px;
  transition: all 0.3s ease;
}

.link-item:hover {
  background-color: var(--mcp-primary);
  color: var(--mcp-textPrimary);
}

/* 中间内容区域样式 */
.center-content {
  flex: 1;
  background-color: var(--mcp-bgPrimary);
}

.main-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid var(--mcp-borderPrimary);
  background-color: var(--mcp-bgPrimary);
}

.header-title {
  font-size: 1.2rem;
  font-weight: 600;
  color: var(--mcp-textPrimary);
}

.main-content {
  padding: 24px;
  height: calc(100vh - 64px); /* 减去header的高度 */
  overflow: hidden; /* 修改为hidden，防止出现双滚动条 */
  background-color: var(--mcp-bgPrimary);
}

.service-status {
  height: 100%;
  overflow: auto; /* 滚动条移到service-status组件内部 */
}

.empty-servers {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 300px;
  color: var(--mcp-textPrimary);
}

:deep(.el-empty__description) {
  color: var(--mcp-textPrimary) !important;
}

:deep(.el-empty__image svg path) {
  fill: var(--mcp-bgSecondary) !important;
}

/* 右侧聊天区域样式 */
.chat-sidebar {
  background-color: var(--mcp-bgPrimary);
  border-left: 1px solid var(--mcp-borderPrimary);
  height: 100vh;
  overflow: hidden; /* 防止外层出现滚动条 */
  display: flex;
  flex-direction: column;
}

/* 确保聊天窗口占满整个侧边栏 */
:deep(.chat-window) {
  flex: 1;
  height: 100%;
  overflow: hidden; /* 防止聊天窗口本身出现滚动条 */
}

/* 响应式布局 */
@media (max-width: 1200px) {
  .left-sidebar {
    width: 200px !important;
  }
}

@media (max-width: 992px) {
  .main-layout {
    flex-direction: column;
  }
  
  .left-sidebar, .chat-sidebar {
    width: 100% !important;
    height: auto;
    max-height: 30vh;
    min-width: unset;
  }
  
  .center-content {
    order: -1;
  }
}

.header-actions {
  display: flex;
  gap: 16px;
  align-items: center;
}

/* 主题切换器容器 */
.theme-switcher-container {
  margin-top: auto;
  padding-top: 16px;
  display: flex;
  justify-content: center;
}
</style> 
