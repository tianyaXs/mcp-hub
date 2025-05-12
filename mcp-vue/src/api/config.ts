import api from './index'
import type { MCPConfig } from '@/types/api'
import { AxiosResponse } from 'axios'

/**
 * 获取MCP配置
 */
export const getMCPConfig = async (): Promise<MCPConfig> => {
  try {
    console.log('正在调用API获取MCP配置...')
    // 因为响应拦截器已经返回了response.data，所以这里接收到的直接是数据
    const response = await api.get('/mcp_config')
    console.log('获取的配置数据完整响应:', response)
    
    // 检查响应结构
    if (!response || typeof response !== 'object') {
      console.error('API响应无效:', response)
      throw new Error('无效的API响应结构')
    }
    
    // 输出结构，便于调试
    console.log('API响应数据:', {
      类型: typeof response,
      结构: JSON.stringify(response, null, 2)
    })
    
    // 直接返回原始响应数据，不做任何转换
    return response as unknown as MCPConfig;
  } catch (error: any) {
    console.error('获取MCP配置失败', error)
    console.error('错误详情:', {
      message: error.message,
      stack: error.stack,
      request: error.request ? '存在' : '不存在',
      response: error.response ? error.response.status : '不存在'
    })
    
    if (error.response && error.response.data && error.response.data.detail) {
      throw error.response.data.detail
    }
    throw typeof error === 'string' ? error : '获取MCP配置失败'
  }
}

/**
 * 更新MCP配置
 */
export const updateMCPConfig = async (config: MCPConfig): Promise<any> => {
  try {
    console.log('开始更新MCP配置...')
    console.log('发送的配置数据:', JSON.stringify(config, null, 2))
    
    // 直接发送配置数据，不做任何转换
    const response = await api.post('/update_mcp_config', config)
    console.log('更新配置完整响应:', response)
    
    // 检查响应结构
    if (!response || typeof response !== 'object') {
      console.error('API响应无效:', response)
      throw new Error('无效的API响应结构')
    }
    
    console.log('更新配置响应结构:', {
      类型: typeof response,
      数据: JSON.stringify(response, null, 2)
    })
    
    // 返回响应数据
    return response
  } catch (error: any) {
    console.error('更新MCP配置失败', error)
    console.error('错误详情:', {
      message: error.message,
      stack: error.stack,
      request: error.request ? '存在' : '不存在',
      response: error.response ? error.response.status : '不存在'
    })
    
    if (error.response && error.response.data && error.response.data.detail) {
      throw error.response.data.detail
    }
    throw typeof error === 'string' ? error : '更新配置失败'
  }
}

/**
 * 注册服务到MCP配置
 */
export const registerMCPServices = async (): Promise<string> => {
  try {
    console.log('开始注册MCP服务...')
    const response = await api.post('/register_mcp_services')
    console.log('注册服务完整响应:', response)
    
    // 检查响应结构
    if (!response || typeof response !== 'object') {
      console.error('API响应无效:', response)
      throw new Error('无效的API响应结构')
    }
    
    console.log('注册服务响应结构:', {
      类型: typeof response,
      数据: JSON.stringify(response, null, 2)
    })
    
    // 响应拦截器已经返回了response.data，所以这里是直接访问属性
    const responseData = response as any;
    
    // 返回消息字符串
    if (responseData && typeof responseData.message === 'string') {
      return responseData.message;
    }
    
    if (responseData && responseData.status === 'success') {
      return '服务注册成功';
    }
    
    return "服务注册成功"
  } catch (error: any) {
    console.error('注册服务失败', error)
    console.error('错误详情:', {
      message: error.message,
      stack: error.stack,
      request: error.request ? '存在' : '不存在',
      response: error.response ? error.response.status : '不存在'
    })
    
    if (error.response && error.response.data && error.response.data.detail) {
      throw error.response.data.detail
    }
    throw typeof error === 'string' ? error : '注册服务失败'
  }
} 
