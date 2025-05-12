import api from './index'
import type { QueryRequest, QueryResponse, ThinkingStep } from '@/types/api'

/**
 * 发送查询请求
 * @param query 用户查询内容
 * @param includeTrace 是否包含思考过程
 * @param onThinkingStep 实时接收思考步骤的回调函数
 */
export const sendQuery = async (
  query: string, 
  includeTrace: boolean = false,
  onThinkingStep?: (step: ThinkingStep) => void
): Promise<{ result: string; trace?: ThinkingStep[] }> => {
  try {
    const data: QueryRequest = { 
      query,
      include_trace: includeTrace,
      stream: !!onThinkingStep // 如果提供了回调函数，则使用流式响应
    }
    
    if (onThinkingStep) {
      // 使用EventSource进行SSE流式接收
      return new Promise((resolve, reject) => {
        // 通过URL查询参数传递查询内容，而不依赖POST请求体
        const queryParams = new URLSearchParams({
          query: query
        }).toString()
        const url = `${api.defaults.baseURL}/query_stream?${queryParams}`
        
        // 创建EventSource，使用GET方法连接
        const eventSource = new EventSource(url)
        let finalResult = ''
        const allSteps: ThinkingStep[] = []
        
        // 一个加载中的步骤ID映射，用于跟踪哪些步骤正在加载
        const loadingSteps: Record<string, boolean> = {}
        
        // 当收到消息时
        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data) as QueryResponse
            
            // 如果是思考步骤
            if (data.thinking_step) {
              const step = data.thinking_step
              
              // 如果是新步骤的开始
              if (step.status === 'start') {
                // 创建一个唯一ID
                step.id = step.id || `step-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
                
                // 将步骤添加到列表
                allSteps.push(step)
                
                // 如果是工具调用，添加一个加载步骤
                if (step.type === 'tool_call') {
                  loadingSteps[step.id] = true
                  // 通知一个加载状态
                  onThinkingStep({
                    type: 'loading',
                    id: `loading-${step.id}`,
                    tool: step.tool,
                    status: 'start'
                  })
                }
                
                // 通知回调
                onThinkingStep(step)
              }
              // 如果是步骤的完成
              else if (step.status === 'complete' && step.id) {
                // 查找并更新步骤
                const existingStep = allSteps.find(s => s.id === step.id)
                if (existingStep) {
                  Object.assign(existingStep, step)
                  
                  // 如果是工具调用完成，移除加载状态
                  if (step.type === 'tool_call' && loadingSteps[step.id]) {
                    delete loadingSteps[step.id]
                    // 通知加载结束
                    onThinkingStep({
                      type: 'loading',
                      id: `loading-${step.id}`,
                      tool: step.tool,
                      status: 'complete'
                    })
                  }
                  
                  // 通知回调
                  onThinkingStep(existingStep)
                }
              }
            }
            
            // 如果是最终结果
            if (data.is_final && data.result) {
              finalResult = data.result
              eventSource.close()
              resolve({ result: finalResult, trace: allSteps })
            }
          } catch (err) {
            console.error('解析SSE消息时出错:', err)
          }
        }
        
        // 连接错误处理
        eventSource.onerror = (err) => {
          console.error('SSE连接错误:', err)
          eventSource.close()
          reject('思考过程连接中断')
        }
        
        // 不再需要额外的fetch POST请求，因为我们已经通过URL查询参数传递了查询内容
      })
    } else {
      // 常规非流式请求
      const response = await api.post<QueryResponse>('/query', data)
      
      // response已经被api.interceptors.response.use处理为响应数据本身
      // 直接使用response作为QueryResponse类型
      const responseData = response as unknown as QueryResponse
      
      return { 
        result: responseData.result,
        trace: responseData.execution_trace 
      }
    }
  } catch (error) {
    if (typeof error === 'string') {
      return { result: `错误: ${error}` }
    }
    return { result: '发送查询请求失败' }
  }
} 
