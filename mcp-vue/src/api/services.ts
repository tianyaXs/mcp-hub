import api from './index'
import type { 
  HealthResponse, 
  ServiceInfoResponse,
  RegisterRequest,
  RegisterResponse,
  Service
} from '@/types/api'

/**
 * 检查服务健康状态
 */
export const checkHealth = async (): Promise<HealthResponse> => {
  return api.get('/health')
}

/**
 * 获取所有服务信息
 */
export const getAllServices = async (): Promise<Service[]> => {
  try {
    const response = await checkHealth()
    if (response && response.connected_services_details) {
      // 将服务详情格式转换为Service类型
      return response.connected_services_details.map(detail => ({
        name: detail.name || detail.url.split('/').slice(-2)[0],
        url: detail.url,
        tools: detail.tools || []
      }))
    }
    return []
  } catch (error) {
    console.error('获取服务列表失败', error)
    return []
  }
}

/**
 * 获取服务详情
 * @param url 服务URL
 */
export const getServiceInfo = async (url: string): Promise<ServiceInfoResponse> => {
  return api.get('/service_info', { params: { url } })
}

/**
 * 注册服务
 * @param data 注册请求数据
 */
export const registerService = async (data: RegisterRequest): Promise<RegisterResponse> => {
  return api.post('/register', data)
}

/**
 * 删除服务
 * @param url 服务URL
 */
export const removeService = async (url: string): Promise<any> => {
  try {
    console.log('正在调用API删除服务:', url)
    const response = await api.post('/remove_service', null, { params: { url } })
    console.log('删除服务响应:', response)
    return response
  } catch (error) {
    console.error('删除服务失败:', error)
    throw error
  }
}

/**
 * 将服务添加到mcp.json并同时注册
 * @param service 服务信息
 */
export const registerToMcpJson = async (service: {
  name: string;
  url: string;
  apiKey?: string;
}): Promise<any> => {
  try {
    console.log('正在添加服务到mcp.json:', service.name);
    
    // 构建mcp.json格式的配置
    const mcpServerConfig: any = {
      url: service.url
    };
    
    // 如果提供了apiKey，添加环境变量
    if (service.apiKey) {
      mcpServerConfig.env = {
        API_KEY: service.apiKey
      };
    }
    
    // 获取当前配置
    const currentConfig = await api.get('/mcp_config');
    const configData = currentConfig as any;
    
    // 确保mcpServers属性存在
    if (!configData.mcpServers) {
      configData.mcpServers = {};
    }
    
    // 添加新服务
    configData.mcpServers[service.name] = mcpServerConfig;
    
    // 更新配置
    const updateResponse = await api.post('/update_mcp_config', configData);
    console.log('mcp.json更新响应:', updateResponse);
    
    // 确保服务已注册
    const registerResponse = await registerService({
      url: service.url,
      name: service.name
    });
    console.log('服务注册响应:', registerResponse);
    
    return {
      status: 'success',
      message: `Service ${service.name} added to mcp.json and registered successfully`,
      updateResponse,
      registerResponse
    };
  } catch (error) {
    console.error('添加服务到mcp.json失败:', error);
    throw error;
  }
}

/**
 * 从mcp.json中删除服务配置
 * @param url 服务URL
 * @param serviceName 可选的服务名称
 */
export const removeServiceFromConfig = async (url: string, serviceName?: string): Promise<any> => {
  try {
    console.log('正在从mcp.json中删除服务:', url);
    
    const params: any = { url };
    if (serviceName) {
      params.service_name = serviceName;
    }
    
    const response = await api.post('/remove_service_from_config', null, { params });
    console.log('从mcp.json删除服务响应:', response);
    
    return response;
  } catch (error) {
    console.error('从mcp.json删除服务失败:', error);
    throw error;
  }
} 
