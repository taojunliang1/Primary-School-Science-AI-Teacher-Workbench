<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, toRaw } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Camera, ChatDotRound, Close, Connection, CopyDocument, DataAnalysis, Delete, EditPen,
  Files, Menu, MoreFilled, Paperclip, Plus, Position, Reading, RefreshRight, Search, Sunny,
} from '@element-plus/icons-vue'
import ChatAttachment from './ChatAttachment.vue'
import ChatMarkdown from './ChatMarkdown.vue'
import { chatPrompts } from '../data/chatPrompts'
import { requestChatReply } from '../data/chatApi'
import { apiMessage } from '../data/todoApi'
import { loadChatState, saveChatState } from '../data/chatStorage'
import '../chat-workspace.css'

const props = defineProps({
  teacherName: { type: String, required: true },
  accountId: Number,
  getToken: { type: Function, required: true },
})
const emit = defineEmits(['insert-into-slides'])
const promptIcons = { Reading, Sunny, Connection, DataAnalysis }
const models = [{ id: 'science', name: 'DeepSeek Flash' }, { id: 'general', name: 'DeepSeek V4 Pro' }]
const imageTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
const fileExtensions = /\.(?:jpe?g|png|webp|gif|pdf|docx|txt|csv|xlsx)$/i
const accept = '.jpg,.jpeg,.png,.webp,.gif,.pdf,.docx,.txt,.csv,.xlsx'
const defaultTitle = '新对话'
const id = () => globalThis.crypto?.randomUUID?.() || Date.now().toString(36) + Math.random().toString(36).slice(2)
const sessions = ref([])
const activeId = ref('')
const query = ref('')
const mobileHistoryOpen = ref(false)
const loading = ref(true)
const storageProblem = ref(false)
const drafts = reactive({})
const jobs = reactive(new Map())
const messageScroll = ref(null)
const composer = ref(null)
const fileInput = ref(null)
const cameraInput = ref(null)
const storageScope = props.accountId ? 'teacher:' + props.accountId : 'state'
let scrollFrame
const active = computed(() => sessions.value.find(session => session.id === activeId.value))
const draft = computed(() => drafts[activeId.value])
const pending = computed(() => jobs.get(activeId.value))
const canSend = computed(() => !!props.accountId && !pending.value && Boolean(draft.value?.text.trim()))

const historyGroups = computed(() => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const recent = new Date(today)
  recent.setDate(today.getDate() - 6)
  const groups = [
    { title: '今天', sessions: [] },
    { title: '近7天', sessions: [] },
    { title: '更早', sessions: [] },
  ]
  const keyword = query.value.trim().toLocaleLowerCase()
  for (const session of [...sessions.value].sort((a, b) => b.updatedAt - a.updatedAt)) {
    if (keyword && ![session.title, ...session.messages.map(item => item.text)].some(text => text.toLocaleLowerCase().includes(keyword))) continue
    const index = session.updatedAt >= +today ? 0 : session.updatedAt >= +recent ? 1 : 2
    groups[index].sessions.push(session)
  }
  return groups.filter(group => group.sessions.length)
})

function ensureDraft(sessionId) {
  drafts[sessionId] ||= { text: '', attachments: [] }
}

function persist() {
  if (loading.value) return
  const snapshot = {
    activeId: activeId.value,
    sessions: sessions.value.map(session => ({
      ...toRaw(session),
      messages: session.messages.map(message => ({
        ...toRaw(message),
        attachments: (message.attachments || []).map(attachment => ({ ...toRaw(attachment) })),
      })),
    })),
  }
  void saveChatState(storageScope, snapshot).catch(() => { storageProblem.value = true })
}

async function scrollToEnd() {
  await nextTick()
  cancelAnimationFrame(scrollFrame)
  scrollFrame = requestAnimationFrame(() => {
    const scrollbar = messageScroll.value
    if (scrollbar?.wrapRef) scrollbar.setScrollTop(scrollbar.wrapRef.scrollHeight)
  })
}

function selectSession(sessionId) {
  ensureDraft(sessionId)
  activeId.value = sessionId
  mobileHistoryOpen.value = false
  persist()
  void scrollToEnd()
}

function newSession() {
  const session = { id: id(), title: defaultTitle, customTitle: false, model: active.value?.model || 'science', updatedAt: Date.now(), messages: [] }
  sessions.value.unshift(session)
  query.value = ''
  selectSession(session.id)
}

onMounted(async () => {
  try {
    const saved = await loadChatState(storageScope)
    if (Array.isArray(saved?.sessions)) {
      sessions.value = saved.sessions
      const initial = sessions.value.find(item => item.id === saved.activeId) || sessions.value[0]
      if (initial) selectSession(initial.id)
    }
  } catch { storageProblem.value = true }
  if (!active.value) newSession()
  loading.value = false
  persist()
  void scrollToEnd()
})
onBeforeUnmount(() => {
  cancelAnimationFrame(scrollFrame)
  jobs.forEach(job => job.controller.abort())
})

async function historyCommand(command, session) {
  if (command === 'rename') {
    let result
    try {
      result = await ElMessageBox.prompt('为这个会话输入一个便于查找的标题。', '重命名对话', {
        inputValue: session.title,
        inputValidator: value => !!value?.trim() && value.trim().length <= 40 || '请输入 1–40 个字符',
        confirmButtonText: '保存', cancelButtonText: '取消',
      })
    } catch { return }
    session.title = result.value.trim()
    session.customTitle = true
  } else if (command === 'delete') {
    try {
      await ElMessageBox.confirm('将删除这段对话及其附件，确定继续？', '删除对话', {
        type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
      })
    } catch { return }
    jobs.get(session.id)?.controller.abort()
    sessions.value = sessions.value.filter(item => item.id !== session.id)
    delete drafts[session.id]
    if (activeId.value === session.id) {
      const next = [...sessions.value].sort((a, b) => b.updatedAt - a.updatedAt)[0]
      if (next) selectSession(next.id)
      else newSession()
    }
  }
  persist()
}

async function clearMessages() {
  const session = active.value
  if (!session?.messages.length) return
  try {
    await ElMessageBox.confirm('将清空此会话的消息及其附件，保留会话标题。', '清空当前对话', {
      type: 'warning', confirmButtonText: '清空', cancelButtonText: '取消',
    })
  } catch { return }
  jobs.get(session.id)?.controller.abort()
  session.messages = []
  session.updatedAt = Date.now()
  persist()
}

function addFiles(event) {
  const files = Array.from(event.target.files || [])
  event.target.value = ''
  if (!draft.value) return
  let rejected = false
  for (const file of files) {
    if (!fileExtensions.test(file.name) || file.size > 10 * 1024 * 1024 || draft.value.attachments.length >= 4) {
      rejected = true
      continue
    }
    const image = imageTypes.includes(file.type) || (!file.type && /\.(jpe?g|png|webp|gif)$/i.test(file.name))
    draft.value.attachments.push({ id: id(), file, name: file.name, image })
  }
  if (rejected) ElMessage.warning('每条消息最多 4 个附件，每个不超过 10 MB。支持常见图片、PDF、DOCX、TXT、CSV 和 XLSX。')
}

function removeAttachment(attachmentId) {
  draft.value.attachments = draft.value.attachments.filter(item => item.id !== attachmentId)
}

async function generate(session, target) {
  if (jobs.has(session.id)) return
  const token = props.accountId && props.getToken()
  if (!token) return ElMessage.warning('请先在工作台首页登录教师账号')
  const controller = new AbortController()
  const model = session.model
  const attempt = target ? (target.attempt || 0) + 1 : 0
  const history = target ? session.messages.slice(0, session.messages.indexOf(target)) : session.messages
  const lastQuestion = history.findLastIndex(message => message.role === 'user' && message.text.trim())
  if (lastQuestion < 0) return ElMessage.warning('请先输入文字问题')
  const messages = history.slice(0, lastQuestion + 1)
  jobs.set(session.id, { controller, targetId: target?.id })
  if (activeId.value === session.id && !target) void scrollToEnd()
  try {
    const result = await requestChatReply({ messages, model, token, signal: controller.signal })
    if (controller.signal.aborted) return
    const reply = { id: target?.id || id(), role: 'assistant', text: result.text, providerModel: result.model, model, attempt, attachments: [] }
    if (target) {
      const index = session.messages.findIndex(message => message.id === target.id)
      if (index >= 0) session.messages.splice(index, 1, reply)
    } else session.messages.push(reply)
    session.updatedAt = Date.now()
    persist()
  } catch (error) {
    if (!controller.signal.aborted) ElMessage.error(apiMessage(error))
  } finally {
    jobs.delete(session.id)
    if (activeId.value === session.id && !target) void scrollToEnd()
  }
}

function send() {
  const session = active.value
  if (!props.accountId) return ElMessage.warning('请先在工作台首页登录教师账号')
  if (!session || !canSend.value) return
  const text = draft.value.text.trim()
  const attachments = draft.value.attachments
  if (!session.messages.length && !session.customTitle) session.title = Array.from(text.replace(/\s+/g, ' ') || attachments[0]?.name || defaultTitle).slice(0, 28).join('')
  session.messages.push({ id: id(), role: 'user', text, attachments })
  session.updatedAt = Date.now()
  draft.value.text = ''
  draft.value.attachments = []
  persist()
  void generate(session)
}

function usePrompt(text, immediate = false) {
  if (!draft.value) return
  draft.value.text = text
  if (immediate) send()
  else composer.value?.focus()
}

function onEnter(event) {
  if (event.shiftKey || event.isComposing || event.keyCode === 229) return
  event.preventDefault()
  send()
}

async function copyMessage(text) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制回复')
  } catch {
    ElMessage.warning('浏览器未允许访问剪贴板，可选中文字后手动复制')
  }
}

function insertIntoSlides(message) {
  const heading = message.text.match(/^#{1,6}\s+(.+)$/m)
  const title = (heading?.[1] || active.value.title).slice(0, 60)
  const content = message.text
    .replace(/^#{1,6}\s+.*\r?\n*/m, '')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/^>\s*/gm, '')
    .replace(/^~~~[^\n]*\n?/gm, '')
    .trim()
  emit('insert-into-slides', { id: id(), title, content })
}
</script>

<template>
  <el-container class="science-chat" aria-label="AI 对话" @keydown.esc="mobileHistoryOpen = false">
    <button v-if="mobileHistoryOpen" class="chat-history-scrim" type="button" aria-label="关闭会话列表" @click="mobileHistoryOpen = false" />
    <el-aside width="260px" class="chat-history" :class="{ 'is-open': mobileHistoryOpen }" aria-label="历史会话">
      <div class="chat-history-top">
        <div class="chat-history-heading"><span class="chat-history-mark"><el-icon><ChatDotRound /></el-icon></span><strong>历史会话</strong></div>
        <el-button class="chat-new-button" :icon="Plus" type="primary" :disabled="loading" @click="newSession">新建对话</el-button>
        <el-input v-model="query" :prefix-icon="Search" placeholder="搜索历史对话" aria-label="搜索历史对话" clearable />
      </div>
      <el-scrollbar class="chat-history-scroll">
        <p v-if="!historyGroups.length && !loading" class="chat-history-empty">没有匹配的会话</p>
        <div v-for="group in historyGroups" :key="group.title" class="chat-history-group">
          <div class="chat-group-label">{{ group.title }}</div>
          <div v-for="session in group.sessions" :key="session.id" class="chat-history-row" :class="{ selected: session.id === activeId }">
            <button class="chat-history-item" type="button" :title="session.title" :aria-current="session.id === activeId ? 'true' : undefined" @click="selectSession(session.id)">
              <el-icon><ChatDotRound /></el-icon><span>{{ session.title }}</span>
            </button>
            <el-dropdown trigger="click" @command="historyCommand($event, session)">
              <button type="button" class="chat-icon-button chat-history-more" :aria-label="'管理对话：' + session.title"><el-icon><MoreFilled /></el-icon></button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item :icon="EditPen" command="rename">重命名</el-dropdown-item>
                  <el-dropdown-item :icon="Delete" command="delete">删除对话</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </el-scrollbar>
      <div class="chat-history-footer"><el-icon><Files /></el-icon>{{ storageProblem ? '当前浏览器无法保存会话' : '会话保存在当前浏览器' }}</div>
    </el-aside>

    <el-container direction="vertical" class="chat-main">
      <header class="chat-header">
        <button type="button" class="chat-icon-button chat-mobile-toggle" aria-label="打开历史会话" :aria-expanded="mobileHistoryOpen" @click="mobileHistoryOpen = !mobileHistoryOpen"><el-icon><Menu /></el-icon></button>
        <div class="chat-heading">
          <span>科学助手</span>
          <h1 :title="active?.title">{{ active?.title || defaultTitle }}</h1>
        </div>
        <span class="chat-demo-badge">DeepSeek</span>
        <div v-if="active" class="chat-header-actions">
          <el-select v-model="active.model" class="chat-model" aria-label="选择 DeepSeek 模型" :disabled="!!pending" @change="persist">
            <el-option v-for="model in models" :key="model.id" :label="model.name" :value="model.id" />
          </el-select>
          <el-tooltip content="清空当前对话">
            <button type="button" class="chat-icon-button chat-clear" aria-label="清空当前对话" :disabled="!active.messages.length" @click="clearMessages"><el-icon><Delete /></el-icon></button>
          </el-tooltip>
        </div>
      </header>

      <el-scrollbar ref="messageScroll" class="chat-messages" :class="{ 'is-empty': !active?.messages.length }">
        <div v-if="loading" class="chat-loading" role="status">正在读取会话…</div>
        <section v-else-if="!active?.messages.length" class="chat-welcome">
          <div class="chat-welcome-copy">
            <span class="chat-welcome-mark" aria-hidden="true">
              <svg viewBox="0 0 48 48" fill="none"><ellipse cx="24" cy="24" rx="19" ry="7.5"/><ellipse cx="24" cy="24" rx="19" ry="7.5" transform="rotate(60 24 24)"/><ellipse cx="24" cy="24" rx="19" ry="7.5" transform="rotate(120 24 24)"/><circle cx="24" cy="24" r="3" fill="currentColor" stroke="none"/></svg>
            </span>
            <p>小学科学 · AI 对话</p>
            <h2>您好，{{ props.teacherName }}。今天想探讨哪个科学课题？</h2>
            <div>从一个科学问题出发，试试课堂设计、现象解释或实验图解。</div>
          </div>
          <div class="chat-prompt-grid" aria-label="科学快捷提问">
            <button v-for="prompt in chatPrompts" :key="prompt.id" type="button" class="chat-prompt-card" @click="usePrompt(prompt.text, true)">
              <span class="chat-prompt-meta"><el-icon><component :is="promptIcons[prompt.icon]" /></el-icon>{{ prompt.category }}</span>
              <strong>{{ prompt.title }}</strong>
              <span class="chat-prompt-text">{{ prompt.text }}</span>
            </button>
          </div>
        </section>
        <section v-else class="chat-thread" aria-label="对话消息">
          <article v-for="message in active.messages" :key="message.id" class="chat-message" :class="'is-' + message.role" :aria-label="message.role === 'assistant' ? '科学助手回复' : props.teacherName + '的消息'">
            <span v-if="message.role === 'assistant'" class="chat-message-avatar chat-ai-avatar" aria-hidden="true"><el-icon><Connection /></el-icon></span>
            <span v-else class="chat-message-avatar chat-teacher-avatar" aria-hidden="true">{{ props.teacherName.slice(0, 1) }}</span>
            <div class="chat-message-content">
              <div v-if="message.role === 'assistant'" class="chat-message-label">科学助手 <span>· {{ message.providerModel || '本地示例' }}</span></div>
              <div class="chat-bubble">
                <ChatMarkdown v-if="message.role === 'assistant'" :text="message.text" />
                <p v-else-if="message.text" class="chat-user-text">{{ message.text }}</p>
                <div v-if="message.attachments.length" class="chat-attachments"><ChatAttachment v-for="attachment in message.attachments" :key="attachment.id" :attachment="attachment" /></div>
              </div>
              <div v-if="message.role === 'assistant'" class="chat-message-actions">
                <button type="button" class="chat-mini-action" @click="copyMessage(message.text)"><el-icon><CopyDocument /></el-icon>复制</button>
                <button type="button" class="chat-mini-action" :disabled="!!pending" @click="generate(active, message)"><el-icon><RefreshRight /></el-icon>重新生成</button>
                <button type="button" class="chat-mini-action" @click="insertIntoSlides(message)"><el-icon><Reading /></el-icon>插入到课件</button>
              </div>
              <div v-else-if="message === active.messages.at(-1) && message.text && !pending && props.accountId" class="chat-message-actions">
                <button type="button" class="chat-mini-action" @click="generate(active)"><el-icon><RefreshRight /></el-icon>重试回复</button>
              </div>
              <p v-if="pending?.targetId === message.id" class="chat-retry-status" role="status">正在重新生成…</p>
            </div>
          </article>
          <div v-if="pending && !pending.targetId" class="chat-message is-assistant" role="status">
            <span class="chat-message-avatar chat-ai-avatar" aria-hidden="true"><el-icon><Connection /></el-icon></span>
            <div class="chat-thinking"><span class="chat-dots" aria-hidden="true"><i /><i /><i /></span>正在等待 DeepSeek 回复</div>
          </div>
        </section>
      </el-scrollbar>

      <footer v-if="draft" class="chat-composer-area">
        <div class="chat-composer">
          <div class="chat-tools">
            <button type="button" class="chat-tool" @click="fileInput?.click()"><el-icon><Paperclip /></el-icon><span>添加附件</span></button>
            <button type="button" class="chat-tool" @click="cameraInput?.click()"><el-icon><Camera /></el-icon><span>拍照 / 图片</span></button>
            <el-dropdown trigger="click" @command="usePrompt($event)">
              <button type="button" class="chat-tool"><span class="chat-slash" aria-hidden="true">/</span><span>快捷指令</span></button>
              <template #dropdown><el-dropdown-menu><el-dropdown-item v-for="prompt in chatPrompts" :key="prompt.id" :command="prompt.text">{{ prompt.title }}</el-dropdown-item></el-dropdown-menu></template>
            </el-dropdown>
            <input ref="fileInput" class="chat-file-input" type="file" :accept="accept" multiple @change="addFiles" />
            <input ref="cameraInput" class="chat-file-input" type="file" accept="image/jpeg,image/png,image/webp,image/gif" capture="environment" @change="addFiles" />
          </div>
          <div v-if="draft.attachments.length" class="chat-draft-files">
            <div v-for="attachment in draft.attachments" :key="attachment.id" class="chat-draft-file">
              <ChatAttachment :attachment="attachment" compact />
              <button type="button" class="chat-icon-button" :aria-label="'移除附件：' + attachment.name" @click="removeAttachment(attachment.id)"><el-icon><Close /></el-icon></button>
            </div>
          </div>
          <el-input ref="composer" v-model="draft.text" type="textarea" :autosize="{ minRows: 1, maxRows: 4 }" resize="none" maxlength="4000" placeholder="输入你的科学教学问题…" aria-label="输入消息" @keydown.enter="onEnter" />
          <div class="chat-send-row">
            <span v-if="props.accountId">Enter 发送 · Shift + Enter 换行</span>
            <span v-else>请先在<a href="#home">工作台首页</a>登录教师账号</span>
            <el-button v-if="pending" class="chat-stop" @click="pending.controller.abort()">停止</el-button>
            <el-button v-else class="chat-send" type="primary" :icon="Position" :disabled="!canSend" @click="send">发送</el-button>
          </div>
        </div>
        <p class="chat-disclaimer">对话文字会发送给 DeepSeek，附件仅在本地预览。请核实 AI 生成的教学内容。</p>
      </footer>
    </el-container>
  </el-container>
</template>
