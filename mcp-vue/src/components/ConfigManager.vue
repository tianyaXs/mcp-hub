<template>
  <div class="config-manager" :class="{'dialog-mode': mode === 'dialog'}">
    <!-- 非对话框模式下显示的标题 -->
    <div class="manager-header" v-if="mode !== 'dialog'">
      <div class="header-content">
        <el-icon class="header-icon"><Setting /></el-icon>
        <h3>配置管理</h3>
      </div>
    </div>
    
    <div class="manager-content">
      <div v-if="loading" class="loading-container">
        <el-skeleton :rows="10" animated />
      </div>
      
      <div v-else>
        <!-- 编辑器 -->
        <div class="editor-container">
          <div class="editor-actions">
            <el-button type="primary" @click="updateConfig" :loading="updating">
              Save and Apply
            </el-button>
            <el-button @click="fetchConfig" :loading="loading">
              Reset
            </el-button>
            <el-button v-if="mode === 'dialog'" @click="closeDialog">
              Cancel
            </el-button>
          </div>
          
          <div class="json-editor">
            <el-input
              v-model="configText"
              type="textarea"
              :rows="20"
              class="editor-textarea"
              :class="{ 'error': hasError }"
              @input="validateJson"
            />
          </div>
          
          <div v-if="hasError" class="error-message">
            <el-alert
              :title="errorMessage"
              type="error"
              show-icon
            />
          </div>
          
          <div v-if="updateResult" class="update-result">
            <el-alert
              :title="updateResult.message"
              :type="updateResult.success ? 'success' : 'error'"
              show-icon
            />
            
            <!-- 如果存在同步结果展示 -->
            <div v-if="updateResult.syncResults" class="sync-results">
              <h4>Service Synchronization Results:</h4>
              <ul>
                <li>Added services: {{ updateResult.syncResults.addedCount || 0 }}</li>
                <li>Removed services: {{ updateResult.syncResults.removedCount || 0 }}</li>
              </ul>
              
              <!-- 新增：详细的同步变更信息 -->
              <div v-if="updateResult.syncResults.details && updateResult.syncResults.details.length > 0" class="sync-details">
                <h5>Details:</h5>
                <div v-for="(item, index) in updateResult.syncResults.details" :key="index" class="sync-item">
                  <el-tag :type="item.success ? 'success' : 'danger'" size="small">
                    {{ item.action === 'add' ? 'Added' : 'Removed' }}
                  </el-tag>
                  <span class="sync-item-name">{{ item.name }}</span>
                  <span class="sync-item-url">{{ item.url }}</span>
                  <span v-if="!item.success" class="sync-item-message">{{ item.message }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, defineProps, defineEmits } from 'vue'
import { useServiceStore } from '../stores/services'
import { ElMessage } from 'element-plus'
import { Setting } from '@element-plus/icons-vue'

const props = defineProps({
  mode: {
    type: String,
    default: 'inline'
  }
})

const emit = defineEmits(['close'])

// 初始化Pinia存储
const serviceStore = useServiceStore()

// 加载状态和配置文本
const loading = ref(true)
const configText = ref('')
const updating = ref(false)
const hasError = ref(false)
const errorMessage = ref('')
const updateResult = ref<{
  success: boolean;
  message: string;
  syncResults?: {
    addedCount: number;
    removedCount: number;
    details: {
      action: string;
      name: string;
      url: string;
      success: boolean;
      message?: string;
    }[];
  }
} | null>(null)

// 初始化时获取配置
onMounted(async () => {
  console.log('💡 ConfigManager组件已挂载，准备获取配置')
  try {
    console.log('📦 serviceStore状态:', {
      isConfigLoaded: serviceStore.isConfigLoaded,
      services: serviceStore.services.length,
      healthy: serviceStore.healthyServices,
    })
    
    console.log('🔄 开始调用fetchConfig方法')
    await fetchConfig()
    console.log('✅ fetchConfig方法执行完成')
  } catch (error) {
    console.error('❌ 配置加载失败:', error)
    ElMessage.error(`配置加载失败: ${error}`)
    loading.value = false
  }
})

// 从存储中获取配置
const fetchConfig = async () => {
  console.log('🔍 fetchConfig方法开始执行...')
  loading.value = true
  
  try {
    console.log('📤 调用store.fetchMCPConfigAction...')
    const config = await serviceStore.fetchMCPConfigAction()
    console.log('📥 从store接收到数据:', config)
    
    if (!config || Object.keys(config).length === 0) {
      console.error('⚠️ 无效的配置数据', config)
      ElMessage.warning('获取到的配置为空或无效，显示默认配置')
      
      // 提供与后端结构一致的默认配置
      configText.value = JSON.stringify({
        "mcpServers": {
          "example-server": {
            "url": "http://example.com:8080"
          },
          "example-weather": {
            "url": "http://example.com:8150"
          }
        }
      }, null, 2)
    } else {
      console.log('🔢 将配置转换为格式化JSON')
      // 直接使用原始格式
      configText.value = JSON.stringify(config, null, 2)
      console.log('📝 配置文本设置完成:', configText.value.substring(0, 100) + '...')
    }
  } catch (error) {
    console.error('❌ 获取配置错误:', error)
    ElMessage.error(`获取配置失败: ${error}`)
    // 提供与后端结构一致的默认配置
    configText.value = JSON.stringify({
      "mcpServers": {
        "example-server": {
          "url": "http://example.com:8080"
        },
        "example-weather": {
          "url": "http://example.com:8150"
        }
      }
    }, null, 2)
  } finally {
    console.log('✅ fetchConfig方法执行完成，loading设置为false')
    loading.value = false
  }
}

// 验证JSON
const validateJson = () => {
  try {
    if (configText.value.trim()) {
      JSON.parse(configText.value)
      hasError.value = false
      errorMessage.value = ''
    }
  } catch (error: any) {
    hasError.value = true
    errorMessage.value = `Invalid JSON: ${error.message}`
  }
}

// 更新配置
const updateConfig = async () => {
  try {
    validateJson()
    if (hasError.value) {
      return
    }
    
    updating.value = true
    updateResult.value = null
    
    const configData = JSON.parse(configText.value)
    const result = await serviceStore.updateMCPConfigAction(configData)
    
    // 处理同步结果
    const syncDetails = serviceStore.syncResults || [];
    const addedCount = syncDetails.filter(item => item.action === 'add' && item.success).length;
    const removedCount = syncDetails.filter(item => item.action === 'remove' && item.success).length;
    
    updateResult.value = {
      success: true,
      message: 'Configuration updated successfully',
      syncResults: {
        addedCount,
        removedCount,
        details: syncDetails
      }
    }
    
    // 刷新服务状态
    await serviceStore.fetchServices()
    await serviceStore.fetchHealthStatus()
    
    if (props.mode === 'dialog') {
      setTimeout(() => {
        emit('close')
      }, 2000)
    }
  } catch (error: any) {
    updateResult.value = {
      success: false,
      message: typeof error === 'string' ? error : 'Failed to update configuration'
    }
    ElMessage.error('Failed to update configuration')
  } finally {
    updating.value = false
  }
}

const closeDialog = () => {
  emit('close')
}
</script>

<style scoped>
.config-manager {
  background-color: var(--mcp-bgPrimary);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.06);
}

.dialog-mode {
  box-shadow: none;
  padding: 0;
  margin: 0;
  border-radius: 0;
}

.manager-header {
  margin-bottom: 20px;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-icon {
  font-size: 24px;
  color: var(--mcp-primary);
}

.manager-header h3 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--mcp-textPrimary);
}

.manager-content {
  margin-top: 16px;
}

.loading-container {
  padding: 20px;
}

.editor-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.editor-actions {
  display: flex;
  gap: 12px;
}

.json-editor {
  position: relative;
}

.editor-textarea {
  width: 100%;
  font-family: monospace;
  border-radius: 8px;
}

.editor-textarea.error {
  border-color: var(--mcp-danger) !important;
}

:deep(.el-textarea__wrapper) {
  background-color: var(--mcp-bgSecondary) !important;
  border-color: var(--mcp-borderSecondary) !important;
}

:deep(.el-textarea__inner) {
  color: var(--mcp-textPrimary) !important;
  background-color: transparent !important;
  font-family: monospace !important;
}

:deep(.el-textarea__inner::placeholder) {
  color: var(--mcp-textSecondary) !important;
}

.error-message,
.update-result {
  margin-top: 16px;
}

.sync-results {
  margin-top: 16px;
  padding: 16px;
  border-radius: 8px;
  background-color: var(--mcp-bgSecondary);
  border: 1px solid var(--mcp-borderSecondary);
}

.sync-results h4 {
  margin: 0 0 12px 0;
  color: var(--mcp-textPrimary);
}

.sync-results ul {
  margin: 0;
  padding-left: 20px;
  color: var(--mcp-textSecondary);
}

.sync-details {
  margin-top: 16px;
}

.sync-details h5 {
  margin: 0 0 8px 0;
  color: var(--mcp-textPrimary);
}

.sync-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  padding: 8px;
  border-radius: 4px;
  background-color: var(--mcp-bgPrimary);
}

.sync-item-name {
  font-weight: 500;
  color: var(--mcp-textPrimary);
}

.sync-item-url {
  color: var(--mcp-textSecondary);
  font-size: 0.9em;
}

.sync-item-message {
  color: var(--mcp-danger);
  font-size: 0.9em;
  margin-left: auto;
}

@media (max-width: 640px) {
  .config-manager {
    padding: 16px;
  }
  
  .editor-actions {
    flex-direction: column;
  }
}
</style> 
