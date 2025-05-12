<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <div class="logo-container">
        <img src="../assets/mcp-logo.svg" alt="MCP Logo" class="logo" />
        <div class="title">MCP Hub</div>
      </div>
      <div class="description">
        Multi-agent Control Protocol Hub
      </div>
    </div>
    
    <div class="sidebar-content">
      <div class="action-section">
        <h3 class="section-title">Tools</h3>
        
        <div class="action-buttons">
          <el-button 
            type="primary" 
            @click="$emit('open-register')" 
            class="action-button"
          >
            <el-icon class="action-icon"><Plus /></el-icon>
            Add Server
          </el-button>
          
          <el-button 
            @click="$emit('open-config')" 
            class="action-button"
          >
            <el-icon class="action-icon"><Setting /></el-icon>
            Manage Config
          </el-button>
        </div>
      </div>
      
      <div class="service-section">
        <div class="section-header">
          <h3 class="section-title">Status</h3>
        </div>
        <div class="service-stats">
          <div class="stat-item">
            <div class="stat-label">Total Services</div>
            <div class="stat-value">{{ serviceCount }}</div>
          </div>
          <div class="stat-item">
            <div class="stat-label">Healthy</div>
            <div class="stat-value">
              <span class="health-badge" :class="{ 'healthy': healthyServiceCount > 0 }">
                {{ healthyServiceCount }}/{{ serviceCount }}
              </span>
            </div>
          </div>
        </div>
      </div>
      
      <div class="resource-section">
        <h3 class="section-title">Resources</h3>
        
        <div class="resource-links">
          <a href="https://composio.dev/docs" target="_blank" class="resource-link">
            <el-icon class="resource-icon"><Document /></el-icon>
            Documentation
          </a>
          
          <a href="https://github.com/mcp-foundation/mcp-hub" target="_blank" class="resource-link">
            <el-icon class="resource-icon"><Link /></el-icon>
            GitHub
          </a>
          
          <a href="https://mcp.composio.dev" target="_blank" class="resource-link">
            <el-icon class="resource-icon"><Location /></el-icon>
            MCP Directory
          </a>
        </div>
      </div>
    </div>
    
    <div class="sidebar-footer">
      <div class="version">Version: 0.1.0</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, defineEmits } from 'vue'
import { useServiceStore } from '@/stores/services'
import { Plus, Setting, Document, Link, Location } from '@element-plus/icons-vue'

defineEmits(['open-register', 'open-config'])

// 初始化
const serviceStore = useServiceStore()

// 计算服务数量和健康服务数量
const serviceCount = computed(() => serviceStore.services.length)
const healthyServiceCount = computed(() => {
  return Object.values(serviceStore.serviceHealth).filter(health => health.healthy).length
})
</script>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: #fff;
  border-right: 1px solid #eaeaea;
  padding: 20px;
  box-sizing: border-box;
}

.sidebar-header {
  margin-bottom: 24px;
}

.logo-container {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}

.logo {
  width: 40px;
  height: 40px;
  margin-right: 12px;
}

.title {
  font-size: 1.5rem;
  font-weight: 600;
  color: #333;
}

.description {
  font-size: 0.9rem;
  color: #666;
  line-height: 1.4;
}

.sidebar-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.section-title {
  font-size: 1.1rem;
  font-weight: 600;
  color: #333;
  margin-top: 0;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #eaeaea;
}

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.action-button {
  width: 100%;
  justify-content: flex-start;
}

.action-icon {
  margin-right: 8px;
}

.service-stats {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background-color: #f5f7fa;
  border-radius: 6px;
}

.stat-label {
  font-size: 0.9rem;
  color: #666;
}

.stat-value {
  font-size: 1rem;
  font-weight: 600;
  color: #333;
}

.health-badge {
  padding: 2px 8px;
  border-radius: 12px;
  background-color: #f56c6c;
  color: white;
  font-size: 0.8rem;
}

.health-badge.healthy {
  background-color: #67c23a;
}

.resource-links {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.resource-link {
  display: flex;
  align-items: center;
  text-decoration: none;
  color: #409EFF;
  padding: 8px 12px;
  border-radius: 6px;
  transition: background-color 0.2s;
}

.resource-link:hover {
  background-color: #ecf5ff;
}

.resource-icon {
  margin-right: 8px;
}

.sidebar-footer {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #eaeaea;
  display: flex;
  justify-content: center;
}

.version {
  font-size: 0.8rem;
  color: #999;
}

@media (max-width: 768px) {
  .sidebar {
    padding: 16px;
  }
  
  .title {
    font-size: 1.3rem;
  }
  
  .logo {
    width: 32px;
    height: 32px;
  }
}
</style> 
