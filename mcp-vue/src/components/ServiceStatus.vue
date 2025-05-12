<template>
  <div class="service-status">
    <div class="status-header">
      <div class="server-status-badge" :class="{'status-healthy': healthyCount > 0, 'status-error': healthyCount === 0}">
        <el-icon v-if="healthyCount > 0"><CircleCheck /></el-icon>
        <el-icon v-else><WarningFilled /></el-icon>
        {{ healthyCount }}/{{ totalCount }} online
      </div>
      
      <el-button 
        @click="refreshStatus" 
        :loading="serviceStore.healthLoading" 
        type="primary" 
        size="small"
        text
      >
        <el-icon><Refresh /></el-icon>
        Refresh
      </el-button>
    </div>
    
    <div class="status-content">
      <el-skeleton v-if="serviceStore.healthLoading && Object.keys(serviceStore.serviceHealth).length === 0" :rows="5" animated />
      
      <template v-else>
        <!-- 服务健康状态表格 -->
        <div v-if="Object.keys(serviceStore.serviceHealth).length > 0" class="service-table">
          <el-table :data="serviceHealthData" stripe style="width: 100%">
            <el-table-column label="Name" prop="name" min-width="130" />
            <el-table-column label="URL" prop="url" min-width="200" show-overflow-tooltip />
            <el-table-column label="Tools" min-width="200">
              <template #default="scope">
                <div class="tool-tags">
                  <el-tag
                    v-for="tool in scope.row.tools"
                    :key="tool"
                    size="small"
                    class="tool-tag"
                    type="info"
                    effect="plain"
                  >
                    {{ tool }}
                  </el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="Status" width="100" align="center">
              <template #default="scope">
                <el-tag :type="scope.row.healthy ? 'success' : 'danger'" size="small">
                  {{ scope.row.healthy ? 'Healthy' : 'Error' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="Last Check" prop="lastCheck" width="160">
              <template #default="scope">
                {{ formatDateTime(scope.row.lastCheck) }}
              </template>
            </el-table-column>
            <el-table-column label="Actions" width="120" align="center">
              <template #default="scope">
                <el-button-group>
                  <el-button type="primary" size="small" text @click="refreshOneService(scope.row.name)">
                    <el-icon><Refresh /></el-icon>
                  </el-button>
                  <el-button type="danger" size="small" text @click="removeService(scope.row.name)">
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </el-button-group>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useServiceStore } from '../stores/services'
import { CircleCheck, WarningFilled, Refresh, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

// 初始化
const serviceStore = useServiceStore()

// 计算健康和总服务数
const healthyCount = computed(() => {
  return Object.values(serviceStore.serviceHealth).filter(service => service.healthy).length
})
const totalCount = computed(() => {
  return Object.keys(serviceStore.serviceHealth).length
})

// 生成表格数据
const serviceHealthData = computed(() => {
  return Object.entries(serviceStore.serviceHealth).map(([name, health]) => ({
    name,
    url: health.url,
    healthy: health.healthy,
    lastCheck: health.lastCheck,
    tools: health.tools || []
  }))
})

// 格式化日期时间
const formatDateTime = (dateStr: string) => {
  try {
    const date = new Date(dateStr)
    return date.toLocaleString()
  } catch (e) {
    return dateStr
  }
}

// 刷新服务状态
const refreshStatus = async () => {
  await serviceStore.fetchHealthStatus()
  ElMessage.success('Status refreshed')
}

// 刷新单个服务状态
const refreshOneService = async (serviceName: string) => {
  // 这里可以添加单个服务刷新逻辑
  await serviceStore.fetchHealthStatus()
  ElMessage.success(`Refreshed ${serviceName}`)
}

// 删除服务
const removeService = (serviceName: string) => {
  ElMessageBox.confirm(
    `Are you sure you want to remove ${serviceName}?`,
    'Warning',
    {
      confirmButtonText: 'Yes',
      cancelButtonText: 'No',
      type: 'warning',
    }
  ).then(async () => {
    try {
      // 查找服务的URL
      const serviceData = serviceHealthData.value.find(service => service.name === serviceName);
      if (!serviceData || !serviceData.url) {
        ElMessage.error(`Cannot find URL for service ${serviceName}`);
        return;
      }
      
      // 调用store方法删除服务
      const response = await serviceStore.removeServiceAction(serviceData.url);
      
      if (response && response.status === 'success') {
        ElMessage.success(response.message || `Removed ${serviceName} successfully`);
      } else {
        ElMessage.warning(`Removed ${serviceName}, but with unexpected response`);
      }
    } catch (error) {
      console.error('Failed to remove service:', error);
      ElMessage.error(`Failed to remove ${serviceName}: ${error}`);
    }
  }).catch(() => {
    // 取消删除
    ElMessage.info('Operation cancelled');
  });
}

// 组件挂载时获取服务状态
onMounted(() => {
  refreshStatus()
})
</script>

<style scoped>
.service-status {
  background-color: var(--mcp-bgPrimary);
  color: var(--mcp-textPrimary);
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden; /* 防止整体出现滚动条 */
}

.status-header {
  flex-shrink: 0; /* 防止头部被压缩 */
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  background-color: var(--mcp-bgSecondary);
  border-bottom: 1px solid var(--mcp-borderSecondary);
}

.server-status-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 16px;
  font-weight: 500;
  font-size: 0.9rem;
  background-color: var(--mcp-bgPrimary);
  color: var(--mcp-textPrimary);
}

.status-healthy {
  background-color: var(--mcp-bgPrimary);
  color: var(--mcp-textPrimary);
}

.status-healthy :deep(.el-icon) {
  color: var(--mcp-success);
}

.status-error {
  background-color: var(--mcp-bgPrimary);
  color: var(--mcp-textPrimary);
}

.status-error :deep(.el-icon) {
  color: var(--mcp-danger);
}

.status-content {
  flex: 1;
  overflow: auto; /* 内容区域可滚动 */
  padding: 16px;
}

.service-table {
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--mcp-borderSecondary);
}

:deep(.el-table) {
  background-color: transparent !important;
  border: none !important;
}

:deep(.el-table__inner-wrapper::before) {
  display: none !important;
}

:deep(.el-table__header) {
  background-color: transparent !important;
}

:deep(.el-table__header-wrapper) {
  border: none !important;
}

:deep(.el-table__header th) {
  background-color: var(--mcp-bgPrimary) !important;
  border-bottom: 1px solid var(--mcp-borderPrimary) !important;
  color: var(--mcp-textPrimary) !important;
  font-weight: normal !important;
}

:deep(.el-table__row) {
  background-color: transparent !important;
}

:deep(.el-table__row:hover > td) {
  background-color: var(--mcp-bgSecondary) !important;
}

:deep(.el-table__body td) {
  background-color: transparent !important;
  border-bottom: 1px solid var(--mcp-borderPrimary) !important;
  color: var(--mcp-textPrimary) !important;
}

:deep(.el-table__empty-block) {
  background-color: transparent !important;
}

:deep(.el-table__empty-text) {
  color: var(--mcp-textSecondary) !important;
}

:deep(.el-table--border) {
  border: none !important;
}

:deep(.el-table--border::after),
:deep(.el-table--border::before) {
  display: none !important;
}

:deep(.el-table--border .el-table__inner-wrapper) {
  border: none !important;
}

:deep(.el-table--border .el-table__cell) {
  border-right: none !important;
}

:deep(.el-table .el-table__cell) {
  padding: 8px 0 !important;
}

:deep(.el-table .el-table__header .el-table__cell) {
  padding: 8px 0 !important;
}

:deep(.el-table td.el-table__cell:first-child),
:deep(.el-table th.el-table__cell:first-child) {
  padding-left: 16px !important;
}

:deep(.el-table td.el-table__cell:last-child),
:deep(.el-table th.el-table__cell:last-child) {
  padding-right: 16px !important;
}

.tool-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.tool-tag {
  background-color: var(--mcp-bgSecondary);
  color: var(--mcp-textPrimary);
  border: 1px solid var(--mcp-borderPrimary);
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 12px;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.status-badge.healthy {
  background-color: var(--mcp-success);
  color: #FFFFFF;
}

.status-badge.error {
  background-color: var(--mcp-danger);
  color: #FFFFFF;
}
</style> 
