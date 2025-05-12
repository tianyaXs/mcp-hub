import { defineStore } from 'pinia'
import { sendQuery } from '@/api/chat'
import type { ThinkingStep } from '@/types/api'

// 定义消息类型
export interface Message {
  content: string
  isUser: boolean
  timestamp: number
  type: 'user' | 'thinking' | 'bot'
  thinking?: ThinkingProcess
}

// 思考过程类型
export interface ThinkingProcess {
  steps: ThinkingStep[]
  isVisible: boolean
  isStreaming: boolean
  isCollapsed: boolean
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    messages: [] as Message[],
    loading: false,
    error: '',
    currentThinking: null as ThinkingProcess | null
  }),
  
  actions: {
    // 添加用户消息
    addUserMessage(content: string) {
      if (!content.trim()) return
      
      // 创建新的思考过程
      const thinking = {
        steps: [],
        isVisible: true,
        isStreaming: true,
        isCollapsed: false
      }
      
      // 添加用户消息
      this.messages.push({
        content,
        isUser: true,
        type: 'user',
        timestamp: Date.now()
      })

      // 添加思考过程消息
      this.messages.push({
        content: '',
        isUser: false,
        type: 'thinking',
        timestamp: Date.now(),
        thinking
      })
      
      // 设置当前思考过程
      this.currentThinking = thinking
      
      // 自动获取回复
      this.getBotResponse(content)
    },
    
    // 添加机器人回复
    addBotMessage(content: string) {
      this.messages.push({
        content,
        isUser: false,
        type: 'bot',
        timestamp: Date.now()
      })
      
      // 清空当前思考过程
      this.currentThinking = null
    },
    
    // 接收单个思考步骤
    receiveThinkingStep(step: ThinkingStep) {
      if (!this.currentThinking) {
        return
      }
      
      // 如果是loading类型，查找并更新
      if (step.type === 'loading' && step.id) {
        const existingLoadingStep = this.currentThinking.steps.find(
          s => s.type === 'loading' && s.id === step.id
        )
        
        if (existingLoadingStep) {
          // 如果状态是完成，则从列表中移除
          if (step.status === 'complete') {
            this.currentThinking.steps = this.currentThinking.steps.filter(
              s => !(s.type === 'loading' && s.id === step.id)
            )
          } else {
            // 否则更新
            Object.assign(existingLoadingStep, step)
          }
          return
        }
      }
      
      // 查找现有步骤
      if (step.id) {
        const existingStep = this.currentThinking.steps.find(s => s.id === step.id)
        if (existingStep) {
          Object.assign(existingStep, step)
          return
        }
      }
      
      // 添加新步骤
      this.currentThinking.steps.push(step)
    },
    
    // 获取机器人回复
    async getBotResponse(userMessage: string) {
      this.loading = true
      this.error = ''
      
      try {
        // 请求中设置包含思考过程
        const response = await sendQuery(
          userMessage, 
          true, 
          // 提供回调函数接收流式思考步骤
          (step) => this.receiveThinkingStep(step)
        )
        
        // 流式接收完成
        if (this.currentThinking) {
          this.currentThinking.isStreaming = false
        }
        
        this.addBotMessage(response.result)
      } catch (error) {
        if (typeof error === 'string') {
          this.error = error
        } else {
          this.error = '获取响应失败'
        }
        this.addBotMessage(`错误: ${this.error}`)
        
        // 错误时也标记流式接收完成
        if (this.currentThinking) {
          this.currentThinking.isStreaming = false
        }
      } finally {
        this.loading = false
      }
    },
    
    // 切换思考过程是否可见
    toggleThinkingVisibility() {
      if (this.currentThinking) {
        this.currentThinking.isVisible = !this.currentThinking.isVisible
      }
    },
    
    // 清空消息历史
    clearMessages() {
      this.messages = []
      this.error = ''
      this.currentThinking = null
    }
  }
}) 
