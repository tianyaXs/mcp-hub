<template>
  <div class="service-register" :class="{'dialog-mode': mode === 'dialog'}">
    <!-- 非对话框模式下显示的标题 -->
    <div class="register-header" v-if="mode !== 'dialog'">
      <div class="header-content">
        <el-icon class="header-icon"><Connection /></el-icon>
        <h3>服务注册</h3>
      </div>
    </div>
    
    <div class="register-content">
      <!-- 服务注册表单 -->
      <el-form :model="customService" label-position="top">
        <el-form-item label="Service URL" required>
          <el-input 
            v-model="customService.url"
            placeholder="Enter service URL, e.g.: http://127.0.0.1:8080/sse"
          />
        </el-form-item>
        
        <el-form-item label="Service Name">
          <el-input 
            v-model="customService.name"
            placeholder="Enter service name (optional)"
          />
        </el-form-item>
        
        <el-form-item label="API Key" v-if="showApiKey">
          <el-input 
            v-model="customService.apiKey"
            placeholder="Enter API key (optional)"
            type="password"
            show-password
          />
        </el-form-item>
        
        <el-form-item v-if="!showApiKey">
          <el-button link type="primary" @click="showApiKey = true">
            <el-icon><Key /></el-icon> Add API Key
          </el-button>
        </el-form-item>
        
        <!-- 响应信息 -->
        <div v-if="resultMessage || errorMessage" class="register-result">
          <el-alert
            v-if="resultMessage"
            :title="resultMessage"
            type="success"
            show-icon
          />
          <el-alert
            v-if="errorMessage"
            :title="errorMessage"
            type="error"
            show-icon
          />
        </div>
        
        <el-form-item>
          <div class="form-actions">
            <el-button 
              type="primary" 
              @click="registerCustomService" 
              :loading="baseStore.loading"
              size="large"
            >
              Register Server
            </el-button>
            
            <el-button 
              @click="registerMCPServices" 
              :loading="serviceStore.registerLoading"
              size="large"
            >
              Register from mcp.json
            </el-button>
            
            <el-button 
              v-if="mode === 'dialog'" 
              @click="closeDialog"
              size="large"
            >
              Cancel
            </el-button>
          </div>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, defineProps, defineEmits } from 'vue'
import { useServiceStore } from '../stores/services'
import { useBaseStore } from '../stores/base'
import { ElMessage } from 'element-plus'
import type { Service } from '../types/api'
import { Connection, Key } from '@element-plus/icons-vue'
import { registerToMcpJson } from '../api/services'

const props = defineProps({
  mode: {
    type: String,
    default: 'standalone' // 'standalone' or 'dialog'
  }
})

const emit = defineEmits(['close'])

// 初始化
const serviceStore = useServiceStore()
const baseStore = useBaseStore()
const resultMessage = ref('')
const errorMessage = ref('')
const showApiKey = ref(false)

// 自定义服务表单数据
const customService = reactive({
  url: '',
  name: '',
  apiKey: ''
})

// 计算服务数量和健康服务数量
const serviceCount = computed(() => serviceStore.services.length)
const healthyServiceCount = computed(() => {
  return Object.values(serviceStore.serviceHealth).filter(health => health.healthy).length
})

// 检查服务是否健康
const isServiceHealthy = (serviceId: string) => {
  return serviceStore.serviceHealth[serviceId]?.healthy || false
}

// 注册MCP服务
const registerMCPServices = async () => {
  try {
    errorMessage.value = ''
    resultMessage.value = ''
    
    const message = await serviceStore.registerMCPServicesAction()
    resultMessage.value = message
    
    if (props.mode === 'dialog') {
      setTimeout(() => {
        emit('close')
      }, 2000)
    }
  } catch (error: any) {
    errorMessage.value = typeof error === 'string' ? error : 'Failed to register services'
  }
}

// 注册自定义服务
const registerCustomService = async () => {
  try {
    errorMessage.value = ''
    resultMessage.value = ''
    
    if (!customService.url.trim()) {
      errorMessage.value = 'Please enter a valid service URL'
      return
    }
    
    baseStore.setLoading(true)
    
    // 构建服务对象
    const serviceData = {
      url: customService.url,
      name: customService.name || customService.url.split('/').slice(-2)[0],
      apiKey: customService.apiKey || undefined
    }
    
    // 直接调用API将服务添加到mcp.json并注册
    const result = await registerToMcpJson(serviceData)
    
    // 刷新服务列表和健康状态
    await serviceStore.fetchServices()
    await serviceStore.fetchHealthStatus()
    
    // 成功后重置表单
    resultMessage.value = result.message || `Service ${serviceData.name} registered successfully`
    customService.url = ''
    customService.name = ''
    customService.apiKey = ''
    showApiKey.value = false
    
    if (props.mode === 'dialog') {
      setTimeout(() => {
        emit('close')
      }, 2000)
    }
  } catch (error: any) {
    errorMessage.value = typeof error === 'string' ? error : 'Failed to register custom service'
  } finally {
    baseStore.setLoading(false)
  }
}

// 关闭对话框
const closeDialog = () => {
  emit('close')
}

// 组件挂载时获取服务和健康状态
onMounted(async () => {
  try {
    // 添加延迟处理，避免路由加载时就发出请求
    setTimeout(async () => {
      try {
        await serviceStore.fetchServices()
        await serviceStore.fetchHealthStatus()
      } catch (error) {
        console.error('Failed to load service information', error)
      }
    }, 500)
  } catch (error) {
    console.error('Failed to load service information', error)
  }
})
</script>

<style scoped>
.service-register {
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

.register-header {
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

.register-header h3 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--mcp-textPrimary);
}

.register-content {
  margin-top: 16px;
}

.register-result {
  margin: 16px 0;
}

.form-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

:deep(.el-form-item__label) {
  color: var(--mcp-textPrimary) !important;
}

:deep(.el-input__wrapper) {
  background-color: var(--mcp-bgSecondary) !important;
  border-color: var(--mcp-borderSecondary) !important;
}

:deep(.el-input__inner) {
  color: var(--mcp-textPrimary) !important;
  background-color: transparent !important;
}

:deep(.el-input__inner::placeholder) {
  color: var(--mcp-textSecondary) !important;
}

@media (max-width: 640px) {
  .service-register {
    padding: 16px;
  }
  
  .form-actions {
    flex-direction: column;
  }
}
</style> 

