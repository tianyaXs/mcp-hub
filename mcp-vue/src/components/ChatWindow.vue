<template>
  <div class="chat-window">
    <div class="chat-window-inner">
      <div class="chat-header">
        <h3>Chat</h3>
        <div class="header-actions">
          <el-button @click="clearChat" type="danger" text size="small">
            <el-icon><Delete /></el-icon>
            Clear
          </el-button>
        </div>
      </div>
      
      <div class="chat-messages" ref="messageContainer">
        <template v-if="chatStore.messages.length">
          <div 
            v-for="(message, index) in chatStore.messages" 
            :key="index"
            :class="['message', getMessageClass(message)]"
          >
            <!-- 普通消息内容 -->
            <div v-if="message.type !== 'thinking'" class="message-content">
              {{ message.content }}
            </div>

            <!-- 思考过程内容 -->
            <div v-else class="thinking-process">
              <div class="thinking-header" @click="toggleThinkingCollapse(message)">
                <div class="thinking-icon">
                  <el-icon v-if="message.thinking?.isStreaming" class="is-loading"><Loading /></el-icon>
                  <el-icon v-else><Check /></el-icon>
                </div>
                <span class="thinking-title">Thinking Process</span>
                <el-icon class="collapse-icon" :class="{ 'is-collapsed': message.thinking?.isCollapsed }">
                  <ArrowDown />
                </el-icon>
              </div>
              
              <el-collapse-transition>
                <div v-show="!message.thinking?.isCollapsed" class="thinking-content">
                  <div class="thinking-steps">
                    <div v-for="(step, stepIndex) in message.thinking?.steps" :key="stepIndex" 
                      :class="['thinking-step', getStepClass(step)]">
                      <div class="step-header">
                        <el-icon v-if="step.type === 'thinking'"><ChatDotRound /></el-icon>
                        <el-icon v-else-if="step.type === 'tool_call'"><Tools /></el-icon>
                        <el-icon v-else class="is-loading"><Loading /></el-icon>
                        
                        {{ getStepTitle(step) }}
                      </div>
                      <div class="step-content">
                        <div v-if="step.type === 'thinking'" class="thinking-text">{{ step.content }}</div>
                        <template v-else-if="step.type === 'tool_call'">
                          <!-- 增强工具调用显示 -->
                          <div class="tool-call-details">
                            <!-- 工具参数，格式化显示JSON -->
                            <div v-if="getToolParams(step)" class="tool-params">
                              <div class="tool-section-title">Parameters:</div>
                              <pre class="json-content">{{ getToolParams(step) }}</pre>
                            </div>
                            
                            <!-- 工具调用结果 -->
                            <div v-if="step.result" class="tool-result">
                              <div class="tool-section-title">Result:</div>
                              <pre>{{ step.result }}</pre>
                            </div>
                            
                            <!-- 工具调用状态标签 -->
                            <el-tag 
                              v-if="step.status" 
                              :type="step.status === 'complete' ? 'success' : 'info'"
                              size="small"
                              class="tool-status-tag"
                            >
                              {{ step.status === 'complete' ? 'Completed' : 'Running' }}
                            </el-tag>
                          </div>
                        </template>
                        <div v-else-if="step.type === 'loading'" class="tool-loading">
                          <el-skeleton :rows="3" animated />
                        </div>
                      </div>
                    </div>
                    
                    <!-- 如果没有思考步骤但正在流式接收 -->
                    <div v-if="message.thinking?.steps.length === 0 && message.thinking?.isStreaming" class="empty-steps">
                      <el-skeleton animated />
                      <div class="loading-text">Thinking...</div>
                    </div>
                  </div>
                </div>
              </el-collapse-transition>
            </div>

            <div class="message-time">
              {{ formatTime(message.timestamp) }}
            </div>
          </div>
        </template>
        <div v-else class="empty-chat">
          <el-empty description="No conversation yet" />
        </div>
        <div v-if="chatStore.loading" class="loading-indicator">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>Thinking...</span>
        </div>
      </div>
      
      <div class="chat-input">
        <el-input
          v-model="inputMessage"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 5 }"
          placeholder="Ask about weather or vehicle controls..."
          :disabled="chatStore.loading"
          @keyup.enter.ctrl="sendMessage"
        />
        <el-button 
          class="send-button" 
          @click="sendMessage" 
          :loading="chatStore.loading" 
          type="primary"
        >
          <el-icon><ChatRound /></el-icon>
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useChatStore } from '../stores/chat'
import type { Message, ThinkingProcess } from '../stores/chat'
import { 
  Loading, 
  Delete, 
  ChatRound, 
  ChatDotRound, 
  Operation, 
  Tools, 
  QuestionFilled,
  ArrowDown,
  Check
} from '@element-plus/icons-vue'
import type { ThinkingStep } from '../types/api'

// 初始化
const chatStore = useChatStore()
const inputMessage = ref('')
const messageContainer = ref<HTMLElement | null>(null)

// 获取步骤的样式类
const getStepClass = (step: ThinkingStep) => {
  if (step.type === 'thinking') return 'thinking-step-thinking'
  if (step.type === 'tool_call') return 'thinking-step-tool'
  if (step.type === 'loading') return 'thinking-step-loading'
  return ''
}

// 获取消息的样式类
const getMessageClass = (message: Message) => {
  if (message.isUser) return 'user-message'
  if (message.type === 'thinking') return 'bot-message thinking-message'
  return 'bot-message'
}

// 获取步骤标题
const getStepTitle = (step: ThinkingStep) => {
  if (step.type === 'thinking') return 'Thinking'
  if (step.type === 'tool_call') return `Using Tool: ${step.tool || ''}`
  if (step.type === 'loading') return `Calling Tool: ${step.tool || ''}`
  return ''
}

// 获取工具参数并格式化为JSON
const getToolParams = (step: ThinkingStep) => {
  if (step.type === 'tool_call' && step.params) {
    return JSON.stringify(step.params, null, 2)
  }
  
  if (step.type === 'tool_call' && step.content) {
    try {
      const paramMatch = step.content.match(/['"]?params['"]?\s*[:=]\s*(\{[^}]+\})/)
      const argsMatch = step.content.match(/['"]?arguments['"]?\s*[:=]\s*(\{[^}]+\})/)
      const jsonMatch = step.content.match(/\{[\s\S]*?\}/)
      
      let paramsJson = null
      if (paramMatch && paramMatch[1]) {
        paramsJson = JSON.parse(paramMatch[1])
      } else if (argsMatch && argsMatch[1]) {
        paramsJson = JSON.parse(argsMatch[1])
      } else if (jsonMatch) {
        try {
          paramsJson = JSON.parse(jsonMatch[0])
        } catch (e) {
          // 如果解析失败，忽略这个错误
        }
      }
      
      if (paramsJson) {
        return JSON.stringify(paramsJson, null, 2)
      }
    } catch (e) {
      console.log('解析工具参数失败:', e)
    }
  }
  return null
}

// 时间格式化函数
const formatTime = (timestamp: number): string => {
  const date = new Date(timestamp)
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

// 发送消息
const sendMessage = () => {
  if (!inputMessage.value.trim() || chatStore.loading) return
  
  chatStore.addUserMessage(inputMessage.value)
  inputMessage.value = ''
}

// 清空聊天记录
const clearChat = () => {
  chatStore.clearMessages()
}

// 监听消息变化，自动滚动到底部
watch(
  () => chatStore.messages.length,
  async () => {
    await nextTick()
    if (messageContainer.value) {
      messageContainer.value.scrollTop = messageContainer.value.scrollHeight
    }
  }
)

// 监听思考过程变化，自动滚动到底部
watch(
  () => chatStore.currentThinking?.steps.length,
  async () => {
    await nextTick()
    if (messageContainer.value) {
      messageContainer.value.scrollTop = messageContainer.value.scrollHeight
    }
  },
  { deep: true }
)

// 切换思考过程的折叠状态
const toggleThinkingCollapse = (message: Message) => {
  if (message.thinking) {
    message.thinking.isCollapsed = !message.thinking.isCollapsed
  }
}
</script>

<style scoped>
.chat-window {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--mcp-bgPrimary);
  overflow: hidden;
}

.chat-window-inner {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 16px;
  padding-right: calc(16px + 8px); /* 基础内边距 + 额外空间，为滚动条预留位置 */
  box-sizing: border-box;
}

.chat-header {
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 0 16px 0;
  border-bottom: 1px solid var(--mcp-borderPrimary);
}

.chat-header h3 {
  margin: 0;
  color: var(--mcp-textPrimary);
  font-size: 1.2rem;
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 16px 0;
  padding-right: 8px; /* 消息区域右侧额外内边距 */
  margin-right: -8px; /* 抵消父元素的额外内边距 */
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100px;
}

.message {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  border-radius: 8px;
  max-width: 85%;
}

.user-message {
  align-self: flex-end;
  background-color: var(--mcp-primary);
  color: var(--mcp-textPrimary);
}

.bot-message {
  align-self: flex-start;
  background-color: var(--mcp-bgSecondary);
  color: var(--mcp-textPrimary);
}

.thinking-message {
  width: 100%;
  max-width: none;
  padding: 0;
  background-color: transparent;
}

.message-content {
  word-break: break-word;
}

.message-time {
  font-size: 0.8rem;
  opacity: 0.8;
  align-self: flex-end;
  padding: 0 12px;
}

.chat-input {
  flex-shrink: 0;
  margin-top: auto;
  display: flex;
  gap: 8px;
  padding-top: 16px;
  border-top: 1px solid var(--mcp-borderPrimary);
  min-height: 60px; /* 确保输入框区域有最小高度 */
  max-height: 150px; /* 限制最大高度 */
  position: relative; /* 添加相对定位 */
  z-index: 1; /* 确保输入框始终在上层 */
}

.thinking-process {
  width: 100%;
  background-color: var(--mcp-bgSecondary);
  border-radius: 8px;
  overflow: hidden;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  color: var(--mcp-textPrimary);
  cursor: pointer;
  user-select: none;
  transition: background-color 0.2s;
}

.thinking-header:hover {
  background-color: var(--mcp-bgTertiary);
}

.thinking-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background-color: var(--mcp-primary);
  color: white;
}

.thinking-icon :deep(.is-loading) {
  animation: rotating 2s linear infinite;
}

@keyframes rotating {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.thinking-title {
  flex: 1;
  font-weight: 500;
}

.collapse-icon {
  transition: transform 0.3s;
}

.collapse-icon.is-collapsed {
  transform: rotate(-90deg);
}

.thinking-content {
  padding: 16px;
  border-top: 1px solid var(--mcp-borderSecondary);
}

.thinking-steps {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.thinking-step {
  padding: 0;
  border: none;
  background: none;
}

.step-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  color: var(--mcp-primary);
  font-weight: 500;
}

.thinking-text {
  padding-left: 16px;
  border-left: 3px solid var(--mcp-primary);
  color: var(--mcp-textSecondary);
  line-height: 1.6;
}

.tool-call-details {
  padding-left: 16px;
  border-left: 3px solid var(--mcp-borderSecondary);
}

.tool-section-title {
  color: var(--mcp-textSecondary);
  font-size: 0.9rem;
  margin-bottom: 8px;
}

.json-content, pre {
  background-color: var(--mcp-bgTertiary);
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto; /* 允许代码块内部滚动 */
  margin: 0;
  font-family: monospace;
  max-width: 100%; /* 防止超出容器 */
  box-sizing: border-box;
}

.tool-status-tag {
  margin-top: 12px;
}

.empty-steps {
  padding-left: 16px;
  border-left: 3px solid var(--mcp-borderSecondary);
}

.empty-chat {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  color: var(--mcp-textSecondary);
}

:deep(.el-empty__description) {
  color: var(--mcp-textSecondary) !important;
}

:deep(.el-empty__image svg path) {
  fill: var(--mcp-bgSecondary) !important;
}

.loading-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--mcp-textSecondary);
  justify-content: center;
  padding: 16px;
}

:deep(.el-input__wrapper) {
  background-color: var(--mcp-bgSecondary) !important;
  border: 1px solid var(--mcp-borderSecondary) !important;
  box-shadow: none !important;
  max-height: 120px; /* 限制输入框最大高度 */
  overflow-y: auto; /* 允许内容滚动 */
}

:deep(.el-input__wrapper:hover) {
  border-color: var(--mcp-primary) !important;
}

:deep(.el-input__wrapper.is-focus) {
  border-color: var(--mcp-primary) !important;
  box-shadow: 0 0 0 1px var(--mcp-primary) !important;
}

:deep(.el-textarea__inner) {
  color: var(--mcp-textPrimary) !important;
  background-color: transparent !important;
  resize: none; /* 禁用手动调整大小 */
  min-height: 36px !important; /* 设置最小高度 */
  max-height: 120px !important; /* 设置最大高度 */
}

:deep(.el-textarea__inner::placeholder) {
  color: var(--mcp-textSecondary) !important;
}

/* 自定义滚动条样式 */
.chat-messages::-webkit-scrollbar {
  width: 8px;
}

.chat-messages::-webkit-scrollbar-track {
  background: var(--mcp-bgSecondary);
  border-radius: 4px;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: var(--mcp-borderSecondary);
  border-radius: 4px;
}

.chat-messages::-webkit-scrollbar-thumb:hover {
  background: var(--mcp-primary);
}
</style> 

