import axios from 'axios'

// 设置基础URL
// 如果.env中有设置VITE_MCP_API_BASE_URL则使用，否则使用默认值
const baseURL = '/api' // 使用代理

// 创建axios实例
const api = axios.create({
  baseURL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    // 在这里可以添加认证信息等
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    let errorMessage = '服务器错误'
    
    if (error.response) {
      const { status, data } = error.response
      
      switch (status) {
        case 400:
          errorMessage = data.detail || '请求参数错误'
          break
        case 404:
          errorMessage = data.detail || '请求的资源不存在'
          break
        case 500:
          errorMessage = data.detail || '服务器内部错误'
          break
        case 502:
          errorMessage = data.detail || '网关错误，服务不可用'
          break
        default:
          errorMessage = data.detail || `HTTP错误: ${status}`
      }
    } else if (error.request) {
      errorMessage = '网络错误，无法连接到服务器'
    }
    
    return Promise.reject(errorMessage)
  }
)

export default api 
