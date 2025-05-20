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
        <template v-if="messages.length">
          <div v-for="(msg, idx) in messages" :key="idx">
            <template v-if="msg.type === 'content'">
              <div :class="['message-row', msg.isUser ? 'user-row' : 'ai-row']">
                <span :class="['msg-content', msg.isUser ? 'user-msg' : 'ai-msg']">{{ msg.content }}</span>
              </div>
            </template>
            <template v-else-if="msg.type === 'ai_reply'">
              <div class="ai-reply-block">
                <div class="thinking-section">
                  <div class="section-title">思考过程</div>
                  <div v-if="msg.thinking.length">
                    <div v-for="(step, sidx) in msg.thinking" :key="step.type === 'thinking' ? step.thinking_id : sidx" class="thinking-step">
                      <template v-if="step.type === 'thinking'">
                        <span class="msg-thinking">🤔 {{ step.content }}</span>
                      </template>
                      <template v-else-if="step.type === 'tool_call'">
                        <div class="toolcall-text">
                          <div>
                            <span class="toolcall-label">Tool:</span>
                            <span class="toolcall-value">{{ step.tool }}</span>
                          </div>
                          <div class="thinking-divider"></div>
                          <template v-if="step.status === 'start'">
                            <div v-if="step.params">
                              <span class="toolcall-label">Params:</span>
                              <pre class="toolcall-value">{{ formatJson(step.params) }}</pre>
                            </div>
                            <div class="thinking-divider"></div>
                          </template>
                          <template v-else-if="step.status === 'complete'">
                            <div v-if="step.result">
                              <span class="toolcall-label">Result:</span>
                              <pre class="toolcall-value">{{ step.result }}</pre>
                            </div>
                            <div class="thinking-divider"></div>
                            <div>
                              <span class="toolcall-label">Status:</span>
                              <span class="toolcall-value">{{ step.status }}</span>
                            </div>
                          </template>
                        </div>
                      </template>
                      <template v-if="sidx < msg.thinking.length - 1">
                        <div class="thinking-divider"></div>
                      </template>
                    </div>
                  </div>
                  <div v-else class="msg-thinking">🤔 AI正在思考...</div>
                </div>
                <div class="final-section" v-if="msg.status === 'done'">
                  <div class="section-title">最终答复</div>
                  <div class="final-answer">{{ msg.final }}</div>
                </div>
              </div>
            </template>
          </div>
        </template>
        <div v-else class="empty-chat">
          <el-empty description="No conversation yet" />
        </div>
        <div v-if="loading" class="loading-indicator">
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
          :disabled="loading"
          @keyup.enter.ctrl="sendMessage"
        />
        <el-button 
          class="send-button" 
          @click="sendMessage" 
          :loading="loading" 
          type="primary"
        >
          <el-icon><ChatRound /></el-icon>
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { sendQueryStreamToken } from '../api/chat'
import { Loading, Delete, ChatRound } from '@element-plus/icons-vue'

interface ThinkingStep {
  type: 'thinking';
  thinking_id: string;
  content: string;
}

interface ToolCallStep {
  type: 'tool_call';
  tool: string;
  params?: any;
  result?: string;
  status?: string;
}

type AiThinkingItem = ThinkingStep | ToolCallStep;

interface AiReplyMessage {
  type: 'ai_reply';
  userQuestion: string;
  thinking: AiThinkingItem[];
  final: string;
  status: 'streaming' | 'done';
}

const inputMessage = ref('')
const messages = ref<(AiReplyMessage | { type: 'content'; content: string; isUser: boolean })[]>([])
const loading = ref(false)
const messageContainer = ref<HTMLElement | null>(null)

const sendMessage = async () => {
  if (!inputMessage.value.trim() || loading.value) return
  // 用户消息单独push
  messages.value.push({ type: 'content', content: inputMessage.value, isUser: true })
  // AI回复结构化分区
  const aiReply: AiReplyMessage = {
    type: 'ai_reply',
    userQuestion: inputMessage.value,
    thinking: [],
    final: '',
    status: 'streaming'
  }
  messages.value.push(aiReply)
  loading.value = true
  await nextTick()
  scrollToBottom()
  await sendQueryStreamToken(inputMessage.value, (token) => {
    console.log('SSE token:', token)
    const lastAiReply = messages.value.filter(m => (m as any).type === 'ai_reply').slice(-1)[0] as AiReplyMessage
    if (!lastAiReply) return
    if (token.type === 'content') {
      // content token 视为最终答复的流式片段，暂不处理
    } else if (token.type === 'thinking') {
      // 如果是thinking_step整合型（带status字段），则跳过，不拼接
      if (token.status) return
      if (!token.thinking_id) return
      let step = lastAiReply.thinking.find(s => s.type === 'thinking' && s.thinking_id === token.thinking_id) as ThinkingStep
      if (step) {
        step.content += token.content
      } else {
        lastAiReply.thinking.push({ type: 'thinking', thinking_id: token.thinking_id, content: token.content })
      }
    } else if (token.type === 'tool_call') {
      // tool_call直接push详细结构
      lastAiReply.thinking.push({
        type: 'tool_call',
        tool: token.tool,
        params: token.params,
        result: token.result,
        status: token.status
      })
    }
    nextTick().then(scrollToBottom)
  }).then((res) => {
    // 最终答复
    const lastAiReply = messages.value.filter(m => (m as any).type === 'ai_reply').slice(-1)[0] as AiReplyMessage
    if (lastAiReply) {
      lastAiReply.final = res.result
      lastAiReply.status = 'done'
    }
    nextTick().then(scrollToBottom)
  })
  loading.value = false
  inputMessage.value = ''
}

const clearChat = () => {
  messages.value = []
}

const scrollToBottom = () => {
  if (messageContainer.value) {
    messageContainer.value.scrollTop = messageContainer.value.scrollHeight
  }
}

const formatJson = (obj: any) => {
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
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
  padding-right: calc(16px + 8px);
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
  padding-right: 8px;
  margin-right: -8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 100px;
}

.message-row {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  gap: 4px;
  padding: 4px 0;
}

.user-row {
  justify-content: flex-end;
}

.ai-row {
  justify-content: flex-start;
}

.msg-content {
  color: var(--mcp-textPrimary);
  background: var(--mcp-bgSecondary);
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 1rem;
  display: inline-block;
  margin-bottom: 2px;
  max-width: 70%;
  word-break: break-word;
}

.user-msg {
  background: var(--mcp-primary);
  color: #fff;
  align-self: flex-end;
}

.ai-msg {
  background: var(--mcp-bgSecondary);
  color: var(--mcp-textPrimary);
  align-self: flex-start;
}

.msg-thinking {
  color: #888;
  margin-left: 8px;
  max-width: 70%;
  word-break: break-word;
  font-family: inherit;
  font-size: 1rem;
}

.msg-tool {
  background: #f6f8fa;
  border-left: 3px solid var(--mcp-primary);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.95rem;
  margin-left: 8px;
  max-width: 70%;
  word-break: break-word;
}

.empty-chat {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  color: var(--mcp-textSecondary);
}

.loading-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--mcp-textSecondary);
  justify-content: center;
  padding: 16px;
}

.ai-reply-block {
  margin: 12px 0;
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid var(--mcp-borderPrimary);
}
.thinking-section {
  background: #f3f6fa;
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 8px;
}
.section-title {
  font-weight: bold;
  color: var(--mcp-primary);
  margin-bottom: 4px;
}
.thinking-step {
  margin-bottom: 4px;
}
.final-section {
  background: #fff;
  border-radius: 6px;
  padding: 10px 12px;
  border: 1px solid #e0e6ed;
}
.final-answer {
  font-size: 1.08rem;
  color: var(--mcp-textPrimary);
  margin-top: 4px;
  word-break: break-word;
}
.toolcall-text {
  font-size: 1rem;
  line-height: 1.6;
  margin: 4px 0 8px 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: inherit;
}
.toolcall-label {
  font-weight: bold;
  color: #1e80ff;
}
.toolcall-value {
  color: #222;
  font-family: inherit;
  font-weight: 500;
}
.toolcall-text pre {
  font-family: inherit;
  font-size: 1rem;
  margin: 0 0 0 24px;
  padding: 0;
  background: none;
  border: none;
  display: block;
  white-space: pre-wrap;
  word-break: break-all;
}
.thinking-divider {
  border-bottom: 1px dashed #e0e6ed;
  margin: 8px 0 8px 0;
  height: 0;
  width: 100%;
  opacity: 0.7;
}
</style> 

