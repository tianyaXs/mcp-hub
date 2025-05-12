import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { 
  checkHealth,
  getServiceInfo,
  registerService,
  getAllServices,
  removeService,
  removeServiceFromConfig
} from '@/api/services'
import {
  getMCPConfig,
  updateMCPConfig,
  registerMCPServices
} from '@/api/config'
import type { HealthResponse, ServiceDetail, MCPConfig, Service, ServiceHealth, RegisterRequest } from '@/types/api'
import { useBaseStore } from './base'

export const useServiceStore = defineStore('services', () => {
  // 基础 store，用于管理全局加载状态
  const baseStore = useBaseStore()

  // 服务状态
  const serviceHealth = ref<{ [key: string]: ServiceHealth }>({})
  // 服务列表
  const services = ref<Service[]>([])
  // MCP配置
  const mcpConfig = ref<MCPConfig | null>(null)
  
  // 同步结果
  const syncResults = ref<Array<{
    action: string;
    name: string;
    url: string;
    success: boolean;
    message: string;
  }>>([])
  
  // 加载状态
  const healthLoading = ref(false)
  const servicesLoading = ref(false)
  const mcpConfigLoading = ref(false)
  const registerLoading = ref(false)
  
  // 计算属性：健康状态
  const healthStatus = computed(() => {
    const status: { [key: string]: boolean } = {}
    Object.keys(serviceHealth.value).forEach((key) => {
      status[key] = serviceHealth.value[key]?.healthy || false
    })
    return status
  })
  
  // 计算属性：服务 URL
  const serviceUrls = computed(() => {
    const urls: { [key: string]: string } = {}
    services.value.forEach((service) => {
      urls[service.name] = service.url
    })
    return urls
  })
  
  // 计算属性：已注册服务名称列表
  const serviceNames = computed(() => {
    return services.value.map((service) => service.name)
  })
  
  // 计算属性：工具统计
  const toolStats = computed(() => {
    let total = 0
    let sseTools = 0
    
    Object.values(serviceHealth.value).forEach(service => {
      if (service.tools) {
        total += service.tools.length
        // 统计SSE相关的工具
        sseTools += service.tools.filter(tool => 
          tool.toLowerCase().includes('sse') || 
          tool.toLowerCase().includes('stream')
        ).length
      }
    })
    
    return {
      total,
      sseTools
    }
  })
  
  // 计算属性：服务统计
  const serviceStats = computed(() => {
    const total = Object.keys(serviceHealth.value).length
    const sseServices = Object.values(serviceHealth.value).filter(service => 
      service.tools?.some(tool => 
        tool.toLowerCase().includes('sse') || 
        tool.toLowerCase().includes('stream')
      )
    ).length
    
    return {
      total,
      sseServices
    }
  })
  
  // 获取服务健康状态
  const fetchHealthStatus = async () => {
    try {
      healthLoading.value = true
      const response = await checkHealth()
      if (response) {
        // 将健康状态响应转换为正确的格式
        const healthData: { [key: string]: ServiceHealth } = {}
        
        if (response.connected_services_details && Array.isArray(response.connected_services_details)) {
          response.connected_services_details.forEach(service => {
            healthData[service.name || service.url] = {
              healthy: service.status === 'healthy',
              lastCheck: new Date().toISOString(),
              url: service.url,
              tools: service.tools || []
            }
          })
        }
        
        serviceHealth.value = healthData
      }
      return response
    } catch (error) {
      console.error('获取服务健康状态失败', error)
      throw error
    } finally {
      healthLoading.value = false
    }
  }
  
  // 注册 MCP 服务
  const registerMCPServicesAction = async (showLoading = true) => {
    try {
      if (showLoading) {
        registerLoading.value = true
        baseStore.setLoading(true)
      }
      
      const message = await registerMCPServices()
      
      // 刷新服务列表和健康状态
      await fetchServices()
      await fetchHealthStatus()
      
      return message
    } catch (error) {
      console.error('注册MCP服务失败', error)
      throw error
    } finally {
      if (showLoading) {
        registerLoading.value = false
        baseStore.setLoading(false)
      }
    }
  }
  
  // 注册自定义服务
  const registerCustomService = async (service: Service) => {
    try {
      baseStore.setLoading(true)
      // 更新 MCP 配置
      if (mcpConfig.value) {
        const config = { ...mcpConfig.value }
        if (!config.services) {
          config.services = {}
        }
        
        config.services[service.name] = service.url
        
        await updateMCPConfigAction(config)
        
        // 刷新服务列表和健康状态
        await fetchServices()
        await fetchHealthStatus()
      } else {
        throw new Error('MCP配置不存在')
      }
    } catch (error) {
      console.error('注册自定义服务失败', error)
      throw error
    } finally {
      baseStore.setLoading(false)
    }
  }
  
  // 获取服务列表
  const fetchServices = async () => {
    try {
      servicesLoading.value = true
      const serviceList = await getAllServices()
      if (serviceList && serviceList.length > 0) {
        services.value = serviceList
      } else {
        services.value = []
      }
      return serviceList
    } catch (error) {
      console.error('获取服务列表失败', error)
      // 出错时不要抛出错误，返回空数组
      services.value = []
      return []
    } finally {
      servicesLoading.value = false
    }
  }
  
  // 获取 MCP 配置
  const fetchMCPConfig = async () => {
    try {
      mcpConfigLoading.value = true
      const response = await getMCPConfig()
      if (response) {
        mcpConfig.value = response
      }
      return response
    } catch (error) {
      console.error('获取MCP配置失败', error)
      throw error
    } finally {
      mcpConfigLoading.value = false
    }
  }
  
  // 获取 MCP 配置 Action (用于组件调用)
  const fetchMCPConfigAction = async () => {
    try {
      const config = await fetchMCPConfig()
      return config
    } catch (error) {
      console.error('获取MCP配置Action失败', error)
      throw error
    }
  }
  
  // 更新 MCP 配置
  const updateMCPConfigAction = async (config: MCPConfig) => {
    try {
      baseStore.setLoading(true)
      
      // 清空之前的同步结果
      syncResults.value = []
      
      // 调用 API 更新配置
      const response = await updateMCPConfig(config)
      
      // 存储配置
      if (response && typeof response === 'object') {
        // 更新本地配置
        mcpConfig.value = config
        
        // 处理同步结果，如果存在
        if (response.sync_results && Array.isArray(response.sync_results)) {
          syncResults.value = response.sync_results
        }
        
        // 刷新服务列表和健康状态
        await fetchServices()
        await fetchHealthStatus()
        
        // 返回消息或默认成功消息
        return response.message || '配置更新成功'
      }
      
      return '配置更新成功'
    } catch (error) {
      console.error('更新MCP配置失败', error)
      throw error
    } finally {
      baseStore.setLoading(false)
    }
  }
  
  // 移除服务
  const removeServiceAction = async (url: string, serviceName?: string) => {
    try {
      baseStore.setLoading(true)
      console.log('从Store中移除服务:', url)
      
      // 尝试从服务列表中查找服务名称
      const existingService = services.value.find(service => service.url === url);
      const serviceNameForLog = serviceName || existingService?.name || url;
      
      // 首先从mcp.json配置中删除服务
      try {
        await removeServiceFromConfig(url, serviceName)
        console.log(`服务 ${serviceNameForLog} 已从mcp.json中删除`)
      } catch (configError) {
        console.warn(`无法从mcp.json中删除服务 ${serviceNameForLog}:`, configError)
        console.warn('将继续尝试删除服务连接')
      }
      
      // 然后调用API删除服务连接
      const response = await removeService(url)
      
      // 刷新服务列表和健康状态
      await fetchServices()
      await fetchHealthStatus()
      
      return response
    } catch (error) {
      console.error('移除服务失败', error)
      throw error
    } finally {
      baseStore.setLoading(false)
    }
  }
  
  return {
    // 状态
    serviceHealth,
    services,
    mcpConfig,
    syncResults,
    
    // 加载状态
    healthLoading,
    servicesLoading,
    mcpConfigLoading,
    registerLoading,
    
    // 计算属性
    healthStatus,
    serviceUrls,
    serviceNames,
    toolStats,
    serviceStats,
    
    // 动作
    fetchHealthStatus,
    registerMCPServicesAction,
    registerCustomService,
    fetchServices,
    fetchMCPConfig,
    fetchMCPConfigAction,
    updateMCPConfigAction,
    removeServiceAction
  }
}) 
