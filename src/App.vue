<script setup>
import { computed, defineAsyncComponent, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Aim, ArrowDown, ArrowLeft, ArrowRight, Bell, Calendar, ChatDotRound,
  Check, CircleCheck, Collection, Compass, Connection, Cpu, DataAnalysis, Delete, Document,
  EditPen, Expand, Fold, HomeFilled, List, Lock, MagicStick, Menu, MoreFilled,
  Notebook, Plus, Reading, Search, Setting, Trophy, User,
  VideoPlay, View,
} from '@element-plus/icons-vue'
import { timetableDays, timetableRows } from './data/timetable'
import { useTodos } from './data/useTodos'
import { apiMessage } from './data/todoApi'
import { applyAccountSchedule, collectScheduleCells, courseType, prepSlotKey, scheduleApi } from './data/scheduleApi'
import SlidesWorkspace from './components/SlidesWorkspace.vue'
import TeachingPrepWorkspace from './components/TeachingPrepWorkspace.vue'
import TodayWorkflow from './components/TodayWorkflow.vue'
const LibraryWorkspace = defineAsyncComponent(() => import('./components/LibraryWorkspace.vue'))
const ChatWorkspace = defineAsyncComponent(() => import('./components/ChatWorkspace.vue'))
const AiPrepWorkspace = defineAsyncComponent(() => import('./components/AiPrepWorkspace.vue'))

const now = ref(new Date())
const teacherName = computed(() => todoTeacher.value?.name || '张老师')
const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
const pad = (value) => String(value).padStart(2, '0')
const dateKey = (date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
const parseDate = (value) => {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day)
}
const todayKey = computed(() => dateKey(now.value))
const selectedDate = ref(todayKey.value)
watch(todayKey, (date, previous) => { if (selectedDate.value === previous) selectedDate.value = date })
const formattedToday = computed(() => `${now.value.getFullYear()}年${now.value.getMonth() + 1}月${now.value.getDate()}日 ${weekdays[now.value.getDay()]}`)
const selectedDateObject = computed(() => parseDate(selectedDate.value))
const selectedDateLabel = computed(() => `${selectedDateObject.value.getMonth() + 1}月${selectedDateObject.value.getDate()}日`)
const selectedWeekday = computed(() => weekdays[selectedDateObject.value.getDay()])
const isToday = computed(() => selectedDate.value === todayKey.value)
const todayColumn = computed(() => now.value.getDay() - 1)
const timetableStorageKey = 'science-workbench-timetable-v1'
const cloneTimetable = (rows) => rows.map((row) => ({
  ...row,
  slots: row.slots?.map((slot) => ({ ...slot })),
}))
const serializeTimetable = (rows) => JSON.stringify(rows.map((row) => row.slots?.map((slot) => (
  slot.skip ? null : { text: slot.text || '', isClass: !!slot.isClass, important: !!slot.important }
)) || null))

function loadTimetable() {
  const rows = cloneTimetable(timetableRows)
  try {
    const saved = JSON.parse(localStorage.getItem(timetableStorageKey) || 'null')
    if (!Array.isArray(saved) || saved.length !== rows.length) return rows
    rows.forEach((row, rowIndex) => row.slots?.forEach((slot, dayIndex) => {
      if (slot.skip) return
      const stored = saved[rowIndex]?.[dayIndex]
      if (!stored || typeof stored.text !== 'string') return
      slot.text = stored.text.slice(0, 60)
      slot.isClass = !!stored.isClass && !!slot.text.trim()
      slot.important = !!stored.important && slot.isClass
    }))
  } catch {
    // 浏览器中没有可用的课表记录时展示样例课表。
  }
  return rows
}

const scheduleRows = ref(loadTimetable())
const scheduleVersion = ref(null)
const scheduleLoading = ref(false)
const scheduleSaving = ref(false)
const scheduleError = ref('')
const selectedPrepSlot = ref(null)
const prepContext = ref(null)
const prepLabels = ref(new Map())
const prepGeneration = ref('')
const prepLinkStatus = ref('loading')
const recentPrepTask = ref(null)
const taskStarted = ref(0)
const chatPrompt = ref(null)
let prepLinkRequest = 0
const timetableDraftRows = ref([])
const editingTimetable = ref(false)
const timetablePromptOpen = ref(false)
const visibleTimetableRows = computed(() => editingTimetable.value ? timetableDraftRows.value : scheduleRows.value)
const hasTimetableEdits = computed(() => editingTimetable.value && serializeTimetable(timetableDraftRows.value) !== serializeTimetable(scheduleRows.value))
const todayCourses = computed(() => scheduleRows.value.filter(row => isPrepSlot(row, row.slots?.[todayColumn.value])).map(row => {
  const key = prepSlotKey(row, todayColumn.value)
  return { key, time: row.time, label: row.slots[todayColumn.value].text, row, lesson: prepLabels.value.get(key) }
}))

function persistTimetable() {
  try {
    localStorage.setItem(timetableStorageKey, serializeTimetable(scheduleRows.value))
    return true
  } catch {
    ElMessage.error('浏览器未能保存课表，请检查存储空间或浏览器设置')
    return false
  }
}

function startTimetableEdit() {
  if (scheduleLoading.value || scheduleSaving.value) return
  timetableDraftRows.value = cloneTimetable(scheduleRows.value)
  editingTimetable.value = true
}

function updateTimetableSlot(rowIndex, dayIndex, value) {
  const slot = timetableDraftRows.value[rowIndex]?.slots?.[dayIndex]
  if (!slot || slot.skip) return
  const wasEmpty = !slot.text?.trim()
  if (slot.text !== value) delete slot.courseType
  slot.text = value.slice(0, 60)
  if (!slot.text.trim()) {
    slot.isClass = false
    slot.important = false
  } else if (wasEmpty && !slot.type) {
    slot.isClass = true
  }
}

async function saveTimetableEdit() {
  if (!hasTimetableEdits.value || scheduleSaving.value || scheduleLoading.value) return
  try {
    await ElMessageBox.confirm(scheduleVersion.value ? '保存修改并同步到当前教师账号？' : '保存本周课表的修改到当前浏览器？', '确认保存课表', {
      confirmButtonText: '保存', cancelButtonText: '继续编辑', type: 'info',
    })
  } catch {
    return
  }
  if (!await saveDisplayedSchedule(cloneTimetable(timetableDraftRows.value))) return
  editingTimetable.value = false
  timetableDraftRows.value = []
  ElMessage.success(scheduleVersion.value ? '账号课表已保存' : '课表已保存到当前浏览器')
}

async function cancelTimetableEdit() {
  if (hasTimetableEdits.value) {
    try {
      await ElMessageBox.confirm('放弃尚未保存的课表修改？', '放弃修改', {
        confirmButtonText: '放弃修改', cancelButtonText: '继续编辑', type: 'warning',
      })
    } catch {
      return
    }
  }
  editingTimetable.value = false
  timetableDraftRows.value = []
}

async function toggleTimetableMark(rowIndex, dayIndex, event) {
  if (editingTimetable.value || scheduleSaving.value || scheduleLoading.value) return
  const row = scheduleRows.value[rowIndex]
  const slot = row?.slots?.[dayIndex]
  if (!slot?.text?.trim() || !slot.isClass) return
  event.preventDefault()
  if (timetablePromptOpen.value) return
  const wasMarked = !!slot.important
  timetablePromptOpen.value = true
  try {
    await ElMessageBox.confirm(`是否${wasMarked ? '取消标记' : '标记'} ${timetableDays[dayIndex]} ${row.time} 的“${slot.text}”？`, wasMarked ? '取消课程标记' : '标记课程', {
      confirmButtonText: wasMarked ? '取消标记' : '确认标记',
      cancelButtonText: wasMarked ? '保留标记' : '取消',
      type: wasMarked ? 'warning' : 'info',
    })
    const rows = cloneTimetable(scheduleRows.value)
    rows[rowIndex].slots[dayIndex].important = !wasMarked
    if (await saveDisplayedSchedule(rows)) ElMessage.success(wasMarked ? '已取消课程标记' : '课程已标记')
  } catch {
    // 用户关闭提示框时保留当前标记状态。
  } finally {
    timetablePromptOpen.value = false
  }
}

const navigation = [
  { label: 'AI 教学工作台', icon: HomeFilled, key: 'home' },
  { group: 'AI 备课中心', icon: MagicStick, items: [
    { label: '备课包与课件精修', icon: MagicStick, key: 'prep' },
    { label: '科学课件生成', icon: Document, key: 'slides' },
    { label: '科学探究设计', icon: Compass, key: 'inquiry' },
  ] },
  { group: 'AI 科学创作台', icon: Connection, items: [
    { label: '科学示意图生成', icon: Connection, key: 'images' },
    { label: '虚拟实验库', icon: Cpu, key: 'experiments', lab: true },
    { label: '教学视频生成', icon: VideoPlay, key: 'videos', lab: true },
  ] },
  { group: 'AI 教研与学情', icon: Reading, items: [
    { label: '教学案例', icon: VideoPlay, key: 'cases' },
    { label: '教研论文', icon: Reading, key: 'papers' },
    { label: '心得体会', icon: Notebook, key: 'reflections' },
    { label: '班级管理', icon: User, key: 'classes', lab: true },
    { label: '实验报告批改', icon: View, key: 'reports', lab: true },
    { label: '课后复盘', icon: Collection, key: 'review', lab: true },
    { label: '科技创新大赛', icon: Trophy, key: 'competition', lab: true },
    { label: '作品集锦', icon: Collection, key: 'works', lab: true },
  ] },
  { group: 'AI 多模态助手', icon: ChatDotRound, items: [
    { label: 'AI 对话', icon: ChatDotRound, key: 'chat' },
    { label: '实验数据分析', icon: DataAnalysis, key: 'analysis' },
    { label: '公式 / 器材识别', icon: Search, key: 'recognition' },
  ] },
]

const skillPrompts = {
  images: '请为小学科学课绘制一张有中文标注的科学示意图。主题是：',
  analysis: '请分析下面的实验数据，列出变化趋势，并指出需要复测的数据。我的数据是：',
  recognition: '请识别我即将上传的照片中的实验器材，说明用途，并列出需要我核对的地方。',
}

const sidebarCollapsed = ref(false)
const workbenchPages = ['prep', 'slides', 'inquiry', 'cases', 'papers', 'reflections', 'chat']
const slideImport = ref(null)
const pageFromHash = () => {
  const key = window.location.hash.slice(1)
  return workbenchPages.includes(key) ? key : 'home'
}
const activePage = ref(pageFromHash())
const mobileSidebarOpen = ref(false)
const mobileSearchOpen = ref(false)
const searchValue = ref('')
const searchInput = ref(null)
const taskPopoverOpen = ref(false)
const expandedGroup = ref('')
watch(activePage, key => { expandedGroup.value = navigation.find(entry => entry.items?.some(item => item.key === key))?.group || '' }, { immediate: true })
const themeKey = 'science-workbench-theme-v1'
const theme = ref(localStorage.getItem(themeKey) === 'plum' ? 'plum' : 'science')
watch(theme, (value) => {
  localStorage.setItem(themeKey, value)
  document.documentElement.classList.toggle('theme-science', value === 'science')
}, { immediate: true })

function toggleTheme() {
  theme.value = theme.value === 'science' ? 'plum' : 'science'
}

function openMobileNav() {
  sidebarCollapsed.value = false
  mobileSidebarOpen.value = true
}

function openFeature(key, label) {
  mobileSidebarOpen.value = false
  if (skillPrompts[key]) {
    chatPrompt.value = { text: skillPrompts[key], model: 'science' }
    key = 'chat'
  }
  if (key === 'home') {
    activePage.value = 'home'
    window.location.hash = 'home'
    nextTick(() => window.scrollTo({ top: 0, behavior: 'smooth' }))
    return
  }
  if (workbenchPages.includes(key)) {
    if (key === 'prep') {
      selectedPrepSlot.value = null
      prepContext.value = null
    }
    activePage.value = key
    window.location.hash = key
    nextTick(() => window.scrollTo({ top: 0, behavior: 'smooth' }))
    return
  }
  if (key === 'todos') {
    activePage.value = 'home'
    window.location.hash = 'home'
    nextTick(() => document.getElementById('todo-card')?.scrollIntoView({ behavior: 'smooth', block: 'center' }))
    return
  }
  ElMessage({ message: `${label}将在后续阶段开放，当前可查看工作台静态预览。`, type: 'info', duration: 2800 })
}

function insertChatIntoSlides(material) {
  slideImport.value = material
  openFeature('slides', '科学课件生成')
}

function openPrepFromDraft(context) {
  openFeature('prep', 'AI 备课中心')
  prepContext.value = context
}

function syncPageFromHash() {
  activePage.value = pageFromHash()
}
let clockTimer
function searchShortcut(event) {
  if (todoTeacher.value && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    mobileSearchOpen.value = true
  }
}
onMounted(() => {
  window.addEventListener('hashchange', syncPageFromHash)
  window.addEventListener('keydown', searchShortcut)
  clockTimer = window.setInterval(() => { now.value = new Date() }, 1000)
})
onUnmounted(() => {
  window.removeEventListener('hashchange', syncPageFromHash)
  window.removeEventListener('keydown', searchShortcut)
  clearInterval(clockTimer)
})

function submitSearch() {
  const query = searchValue.value.replace(/\s+/g, '').toLowerCase()
  if (!query) return
  const all = [{ key: 'home', label: '首页 工作台 课表' }, { key: 'todos', label: '每日待办' }, { key: 'prep', label: 'AI 备课中心' }, ...navigation.flatMap((entry) => entry.items || [entry])]
  const match = all.find((item) => item.label.replace(/\s+/g, '').toLowerCase().includes(query))
  if (match) openFeature(match.key, match.label)
  else {
    chatPrompt.value = { text: searchValue.value.trim(), model: 'science' }
    openFeature('chat', 'AI 对话')
  }
  searchValue.value = ''
  mobileSearchOpen.value = false
}

const {
  teacher: todoTeacher, credentials: todoCredentials, restoringSession, signingIn, loginError, listError: todoError, getChatToken,
  loading: todoLoading, busy: todoBusy, refresh: refreshTodos, login: loginTodos, logout: logoutTodos,
  todoInput, todoPriority, todayPendingCount, visibleTodos, completedCount, pendingCount, progress,
  legacyCount, importLegacy, addTodo, editTodo, toggleTodo, removeTodo, completeAll, clearCompleted,
} = useTodos(selectedDate, todayKey)
const loginPassword = ref(null)

async function refreshPrepLinks() {
  const token = getChatToken()
  if (!token) return
  const query = ++prepLinkRequest
  prepLinkStatus.value = 'loading'
  try {
    const [links, lessons] = await Promise.all([scheduleApi.prepLinks(token), scheduleApi.prepLessons(token)])
    if (token !== getChatToken() || query !== prepLinkRequest) return
    const byId = new Map(lessons.map(lesson => [lesson.id, lesson]))
    prepLabels.value = new Map(links.map(link => [link.slotKey, byId.get(link.lessonId)]))
    prepLinkStatus.value = 'ready'
  } catch {
    if (token === getChatToken() && query === prepLinkRequest) {
      prepLabels.value = new Map()
      prepLinkStatus.value = 'error'
    }
  }
}

async function loadAccountSchedule() {
  const token = getChatToken()
  if (!token || scheduleLoading.value || scheduleSaving.value || editingTimetable.value) return
  scheduleLoading.value = true
  scheduleError.value = ''
  try {
    const result = await scheduleApi.read(token)
    if (token !== getChatToken()) return
    scheduleVersion.value = result.version
    if (result.version) scheduleRows.value = applyAccountSchedule(cloneTimetable(timetableRows), result.cells)
  } catch (error) {
    if (token === getChatToken()) scheduleError.value = apiMessage(error)
  } finally {
    if (token === getChatToken()) scheduleLoading.value = false
  }
}

async function saveDisplayedSchedule(rows, syncFirstTime = false) {
  if (scheduleSaving.value || scheduleLoading.value) return false
  if (!scheduleVersion.value && !syncFirstTime) {
    const previous = scheduleRows.value
    scheduleRows.value = rows
    if (persistTimetable()) return true
    scheduleRows.value = previous
    return false
  }
  const token = getChatToken()
  if (!token) return false
  scheduleSaving.value = true
  scheduleError.value = ''
  try {
    const result = await scheduleApi.save(token, scheduleVersion.value, collectScheduleCells(rows))
    if (token !== getChatToken()) return false
    scheduleVersion.value = result.version
    scheduleRows.value = applyAccountSchedule(cloneTimetable(timetableRows), result.cells)
    return true
  } catch (error) {
    if (token === getChatToken()) {
      scheduleError.value = apiMessage(error)
      ElMessage.error(scheduleError.value)
    }
    return false
  } finally {
    if (token === getChatToken()) scheduleSaving.value = false
  }
}

async function syncBrowserSchedule() {
  try {
    await ElMessageBox.confirm('将当前浏览器的周课表复制到教师账号，原本的浏览器副本继续保留。', '同步课表', {
      confirmButtonText: '同步', cancelButtonText: '取消', type: 'info',
    })
  } catch { return }
  if (!scheduleVersion.value && await saveDisplayedSchedule(scheduleRows.value, true)) ElMessage.success('账号课表已同步')
}

function isPrepSlot(row, slot) {
  return !row.band && slot?.text?.trim() && courseType(slot) === 'regular'
}

function openSlotPrep(row, dayIndex) {
  const key = prepSlotKey(row, dayIndex)
  openFeature('prep', 'AI 备课中心')
  selectedPrepSlot.value = {
    key, label: `${timetableDays[dayIndex]} ${row.time} · ${row.slots[dayIndex].text}`,
    lessonId: prepLabels.value.get(key)?.id || null,
  }
}

watch(() => todoTeacher.value?.id, id => {
  scheduleVersion.value = null
  scheduleRows.value = loadTimetable()
  timetableDraftRows.value = []
  editingTimetable.value = false
  scheduleLoading.value = false
  scheduleSaving.value = false
  scheduleError.value = ''
  prepLabels.value = new Map()
  prepLinkRequest++
  prepLinkStatus.value = 'loading'
  chatPrompt.value = null
  recentPrepTask.value = null
  prepGeneration.value = ''
  selectedPrepSlot.value = null
  prepContext.value = null
  if (id) {
    void loadAccountSchedule()
    void refreshPrepLinks()
  }
})

function moveDate(offset) {
  const target = parseDate(selectedDate.value)
  target.setDate(target.getDate() + offset)
  selectedDate.value = dateKey(target)
}

function reportPrepTask(status) {
  if (status && !prepGeneration.value) {
    taskStarted.value = Date.now()
    recentPrepTask.value = null
  }
  prepGeneration.value = status
}

function openTaskResult() {
  taskPopoverOpen.value = false
  activePage.value = 'prep'
  window.location.hash = 'prep'
}

</script>

<template>
  <div v-if="todoTeacher" class="app-shell" :class="{ 'sidebar-collapsed': sidebarCollapsed, 'mobile-nav-open': mobileSidebarOpen }">
    <div v-if="mobileSidebarOpen" class="mobile-scrim" @click="mobileSidebarOpen = false" />
    <aside class="sidebar">
      <div class="brand" @click="openFeature('home', '工作台首页')">
        <div class="brand-mark"><el-icon><Aim /></el-icon></div>
        <div v-if="!sidebarCollapsed" class="brand-copy">
          <strong>科学教师工作台</strong>
          <span>AI Science Workbench</span>
        </div>
      </div>
      <div class="sidebar-scroll">
        <nav aria-label="主导航">
          <template v-for="entry in navigation" :key="entry.group || entry.key">
            <button v-if="entry.key" class="nav-link" :class="{ selected: activePage === entry.key }" type="button" @click="openFeature(entry.key, entry.label)" :title="entry.label">
              <el-icon><component :is="entry.icon" /></el-icon><span v-if="!sidebarCollapsed">{{ entry.label }}</span>
            </button>
            <div v-else class="nav-group">
              <button class="nav-link workspace-group" type="button" :title="entry.group" :aria-expanded="expandedGroup === entry.group" @click="expandedGroup = expandedGroup === entry.group ? '' : entry.group"><el-icon><component :is="entry.icon" /></el-icon><span v-if="!sidebarCollapsed">{{ entry.group }}</span><el-icon v-if="!sidebarCollapsed" class="workspace-chevron"><ArrowDown /></el-icon></button>
              <button v-for="item in (expandedGroup === entry.group ? entry.items : [])" :key="item.key" class="nav-link workspace-child" :class="{ selected: activePage === item.key }" type="button" @click="openFeature(item.key, item.label)" :title="item.label + (item.lab ? ' · 规划中' : '')">
                <el-icon><component :is="item.icon" /></el-icon><span v-if="!sidebarCollapsed">{{ item.label }}<small v-if="item.lab">规划中</small></span>
              </button>
            </div>
          </template>
        </nav>
      </div>
      <div class="sidebar-footer">
        <div class="sidebar-footer-card" v-if="!sidebarCollapsed">
          <el-icon><MagicStick /></el-icon>
          <div><strong>让好奇心发光</strong><span>让每一堂科学课更精彩</span></div>
        </div>
        <button class="collapse-btn" type="button" :aria-label="sidebarCollapsed ? '展开侧栏' : '收起侧栏'" @click="sidebarCollapsed = !sidebarCollapsed">
          <el-icon><Expand v-if="sidebarCollapsed" /><Fold v-else /></el-icon>
          <span v-if="!sidebarCollapsed">收起导航</span>
        </button>
      </div>
    </aside>

    <div class="workspace">
      <header class="topbar">
        <div class="topbar-left">
          <button class="mobile-menu icon-button" type="button" aria-label="打开导航" @click="openMobileNav"><el-icon><Menu /></el-icon></button>
          <div class="page-heading"><span class="page-name">小学科学 AI 教师工作台</span><span class="top-date">{{ formattedToday }}</span></div>
        </div>
        <div class="topbar-actions">
          <div class="search-box"><el-icon><Search /></el-icon><input v-model="searchValue" placeholder="搜功能，或向 AI 提问" aria-label="搜索功能或向 AI 提问" @keyup.enter="submitSearch" /><kbd>Ctrl K</kbd></div>
          <button class="mobile-search icon-button" type="button" aria-label="搜索功能" @click="mobileSearchOpen = true"><el-icon><Search /></el-icon></button>
          <el-popover v-model:visible="taskPopoverOpen" placement="bottom-end" :width="286" trigger="click">
            <template #reference><button class="task-status" type="button"><span class="task-pulse" :class="{ idle: !prepGeneration }" /> <span>{{ prepGeneration ? '1 个备课任务' : 'AI 任务' }}</span></button></template>
            <div class="popover-task"><div class="popover-title">本标签页 · AI 备课任务</div><p aria-live="polite">{{ prepGeneration || recentPrepTask || '暂无备课任务。' }}</p><small v-if="prepGeneration">已用 {{ Math.max(0, Math.floor((now.getTime() - taskStarted) / 1000)) }} 秒</small><el-button v-if="prepGeneration || recentPrepTask" text type="primary" @click="openTaskResult">返回备课现场</el-button></div>
          </el-popover>
          <el-tooltip content="通知中心将在后续阶段开放" placement="bottom"><button class="icon-button notification-btn" type="button" @click="openFeature('notifications', '通知中心')"><el-icon><Bell /></el-icon><i /></button></el-tooltip>
          <el-dropdown trigger="click">
            <button class="user-trigger" type="button"><span class="avatar">鹤</span><span class="user-name">{{ teacherName }}</span><el-icon><ArrowDown /></el-icon></button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item :icon="User" @click="openFeature('profile', '个人资料')">个人资料</el-dropdown-item>
                <el-dropdown-item :icon="Aim" @click="toggleTheme">{{ theme === 'science' ? '切换至原配色' : '切换至青绿主题' }}</el-dropdown-item>
                <el-dropdown-item :icon="Setting" @click="openFeature('settings', '系统设置')">系统设置</el-dropdown-item>
                <el-dropdown-item divided :disabled="todoBusy" @click="logoutTodos">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <KeepAlive>
        <ChatWorkspace v-if="activePage === 'chat'" :key="todoTeacher?.id || 'guest'" :teacher-name="teacherName" :account-id="todoTeacher?.id" :get-token="getChatToken" :prompt-request="chatPrompt" @prompt-consumed="chatPrompt = null" @insert-into-slides="insertChatIntoSlides" />
      </KeepAlive>
      <KeepAlive>
        <SlidesWorkspace v-if="activePage === 'slides'" :chat-import="slideImport" @chat-imported="slideImport = null"
          @ai-prep="openPrepFromDraft" @back="openFeature('home', '工作台首页')" />
      </KeepAlive>
      <KeepAlive :key="todoTeacher?.id || 'guest'">
        <AiPrepWorkspace v-if="activePage === 'prep'" :account-id="todoTeacher?.id"
          :get-token="getChatToken" :selected-slot="selectedPrepSlot" :initial-context="prepContext" @links-changed="refreshPrepLinks"
          @generation-state="reportPrepTask" @task-result="recentPrepTask = $event" />
      </KeepAlive>
      <TeachingPrepWorkspace v-if="activePage === 'inquiry'" :key="activePage" :mode="activePage"
        @ai-prep="openPrepFromDraft" @back="openFeature('home', '工作台首页')" />
      <LibraryWorkspace v-else-if="['cases', 'papers', 'reflections'].includes(activePage)" :key="activePage" :mode="activePage" @back="openFeature('home', '工作台首页')" />
      <main v-else-if="activePage === 'home'" class="dashboard">
        <section class="welcome-banner" aria-label="今日欢迎">
          <div class="welcome-content"><div class="welcome-eyebrow"><span class="eyebrow-dot" />{{ now.getMonth() + 1 }}月{{ now.getDate() }}日 · 今日科学</div><h1>欢迎{{ teacherName }}，美好的一天从探索开始</h1><p><template v-if="scheduleLoading || scheduleError">{{ scheduleLoading ? '正在读取课表。' : '账号课表暂时无法读取。' }}</template><template v-else>{{ scheduleVersion ? '账号课表' : '浏览器课表' }}今天有 <strong>{{ todayCourses.length }} 节科学课</strong>。</template><template v-if="todayPendingCount !== null && !todoError"><strong>{{ todayPendingCount }} 项任务</strong>待办。</template><template v-else>今日待办正在核对。</template></p></div>
          <div class="banner-art" aria-hidden="true"><div class="orbit orbit-one"/><div class="orbit orbit-two"/><div class="planet planet-one"/><div class="planet planet-two"/><div class="planet planet-three"/><span class="sparkle sparkle-one">✧</span><span class="sparkle sparkle-two">✦</span><span class="sparkle sparkle-three">✧</span></div>
        </section>

        <TodayWorkflow :courses="todayCourses" :date="todayKey" :get-token="getChatToken" :account-id="todoTeacher.id"
          :status="scheduleError ? 'error' : scheduleLoading ? 'loading' : prepLinkStatus" :synced="Boolean(scheduleVersion)"
          @retry="loadAccountSchedule(); refreshPrepLinks()" @open-slot="openSlotPrep($event.row, todayColumn)" @open-feature="openFeature"
          @imported="selectedDate = todayKey; refreshTodos()" />

        <div class="content-grid">
          <section class="course-card surface-card" aria-labelledby="course-title">
            <div class="card-header"><div class="card-title-wrap"><span class="heading-icon rose"><el-icon><Calendar /></el-icon></span><div><span class="overline">WEEKLY TIMETABLE</span><h2 id="course-title">今日课程 · 本周课表</h2></div></div><div class="timetable-header-actions"><span class="schedule-week-label">{{ formattedToday }}</span><el-button v-if="todoTeacher && !editingTimetable && !scheduleVersion" size="small" :loading="scheduleSaving" :disabled="scheduleLoading" @click="syncBrowserSchedule">同步到账号</el-button><el-button v-if="!editingTimetable" size="small" :icon="EditPen" :disabled="scheduleLoading || scheduleSaving" @click="startTimetableEdit">编辑课表</el-button></div></div>
            <div v-if="scheduleError" class="timetable-edit-bar" role="alert"><span>{{ scheduleError }}</span><el-button v-if="!editingTimetable" size="small" @click="loadAccountSchedule">重新读取</el-button></div>
            <div v-if="editingTimetable" class="timetable-edit-bar"><span>点击课程格修改内容，空白格也可填写。{{ scheduleVersion ? '保存到当前账号。' : '先保存到浏览器，可再同步到账号。' }}</span><div><el-button size="small" :disabled="scheduleSaving" @click="cancelTimetableEdit">放弃修改</el-button><el-button type="primary" size="small" :icon="Check" :loading="scheduleSaving" :disabled="!hasTimetableEdits" @click="saveTimetableEdit">保存修改</el-button></div></div>
            <div class="timetable-scroll" role="region" aria-label="本周课程表，可横向滚动" tabindex="0">
              <div class="timetable-inner">
              <table class="timetable">
                <thead><tr><th colspan="2" scope="col">时间</th><th v-for="(day, index) in timetableDays" :key="day" scope="col" :class="{ 'today-column': index === todayColumn }">{{ day }}<span v-if="index === todayColumn" class="day-today-dot" aria-label="今天" /></th></tr></thead>
                <tbody>
                  <tr v-for="(row, rowIndex) in visibleTimetableRows" :key="row.time" :class="`row-${row.band || 'regular'}`">
                    <th v-if="row.section" class="section-time" scope="row" :rowspan="row.sectionRowspan || 1">{{ row.section }}</th>
                    <th class="clock-time" scope="row" :colspan="row.section || row.sectionContinue ? 1 : 2">{{ row.time }}</th>
                    <td v-if="row.merged" class="merged-event" colspan="5">{{ row.merged }}</td>
                    <template v-else v-for="(slot, dayIndex) in row.slots" :key="dayIndex">
                      <td v-if="!slot.skip" :rowspan="slot.rowSpan || 1" :class="['schedule-slot', { 'today-column': dayIndex === todayColumn, 'research-slot': slot.type === 'research', 'markable-slot': !editingTimetable && slot.isClass && slot.text, 'marked-slot': slot.important }]" :title="!editingTimetable && slot.isClass && slot.text ? (slot.important ? '右键取消标记' : '右键添加标记') : undefined" @contextmenu="toggleTimetableMark(rowIndex, dayIndex, $event)">
                        <input v-if="editingTimetable" class="slot-editor" type="text" :value="slot.text || ''" maxlength="60" placeholder="＋" :aria-label="`编辑${timetableDays[dayIndex]}${row.time}课程`" @input="updateTimetableSlot(rowIndex, dayIndex, $event.target.value)" />
                        <template v-else-if="slot.text">
                          <span :class="['slot-label', { 'important-lesson': slot.important, 'event-label': slot.isClass === false }]">{{ slot.text }}</span>
                          <button v-if="todoTeacher && isPrepSlot(row, slot)" class="slot-prep-link" type="button"
                            :title="prepLabels.get(prepSlotKey(row, dayIndex))?.title || '为这节课关联备课包'"
                            :aria-label="`${timetableDays[dayIndex]} ${row.time} ${slot.text}：${prepLabels.get(prepSlotKey(row, dayIndex))?.title || 'AI 备课'}`"
                            @click="openSlotPrep(row, dayIndex)">{{ prepLabels.get(prepSlotKey(row, dayIndex))?.title || 'AI 备课' }}<template v-if="dayIndex === todayColumn && prepLabels.get(prepSlotKey(row, dayIndex))?.revision"> · v{{ prepLabels.get(prepSlotKey(row, dayIndex)).revision }}</template></button>
                        </template>
                      </td>
                    </template>
                  </tr>
                </tbody>
              </table>
              <div v-if="todayColumn >= 0 && todayColumn < 5" class="today-column-outline" :style="{ gridColumn: `${todayColumn + 2} / span 1` }" aria-hidden="true" />
              </div>
            </div>
            <div class="timetable-legend"><span><i class="legend-dot key-lesson" />已标记课程</span><span><i class="legend-dot today-day" />今天</span><span class="legend-note">右键课程可标记 · {{ scheduleVersion ? '账号课表' : '浏览器课表' }}</span></div>
          </section>

          <section id="todo-card" class="todo-card surface-card" aria-labelledby="todo-title">
            <div class="card-header">
              <div class="card-title-wrap"><span class="heading-icon peach"><el-icon><List /></el-icon></span><div><span class="overline">DAILY PLANNER</span><h2 id="todo-title">每日待办</h2></div></div>
              <span v-if="!todoLoading && !todoError" class="pending-pill">{{ pendingCount }} 项待办</span>
            </div>
            <div v-if="legacyCount" class="todo-import"><span>本浏览器有 {{ legacyCount }} 项旧待办</span><el-button size="small" :disabled="todoBusy" @click="importLegacy">导入旧待办</el-button></div>
            <div class="date-switcher"><button type="button" aria-label="前一天" @click="moveDate(-1)"><el-icon><ArrowLeft /></el-icon></button><div><el-icon><Calendar /></el-icon><strong>{{ selectedDateLabel }}</strong><span>{{ selectedWeekday }}</span><span v-if="isToday" class="today-marker">今天</span></div><button type="button" aria-label="后一天" @click="moveDate(1)"><el-icon><ArrowRight /></el-icon></button></div>
            <div v-if="todoLoading" class="todo-empty" role="status"><p>正在读取待办…</p></div>
            <div v-else-if="todoError" class="todo-empty" role="alert"><p>{{ todoError }}</p><el-button size="small" @click="refreshTodos">重试</el-button></div>
            <template v-else>
              <div class="todo-stats"><span>共 <strong>{{ visibleTodos.length }}</strong> 项 · 已完成 <strong>{{ completedCount }}</strong> · 未完成 <strong>{{ pendingCount }}</strong></span><span><strong>{{ progress }}%</strong></span></div>
              <el-progress :percentage="progress" :show-text="false" :stroke-width="5" :color="theme === 'science' ? '#10B981' : '#a87b89'" />
              <div class="todo-list" v-if="visibleTodos.length">
                <div v-for="todo in visibleTodos" :key="todo.id" class="todo-row" :class="{ done: todo.done }">
                  <el-checkbox :model-value="todo.done" :disabled="todoBusy" :aria-label="'完成' + todo.content" @change="toggleTodo(todo, $event)" />
                  <span class="todo-text" @dblclick="editTodo(todo)">{{ todo.content }}</span>
                  <el-tag v-if="todo.priority !== 'normal'" :type="todo.priority === 'high' ? 'danger' : 'info'" size="small" effect="plain" round>{{ todo.priority === 'high' ? '重要' : '低' }}</el-tag>
                  <el-dropdown trigger="click" :disabled="todoBusy">
                    <button class="todo-more" type="button" :disabled="todoBusy" :aria-label="'管理待办：' + todo.content"><el-icon><MoreFilled /></el-icon></button>
                    <template #dropdown><el-dropdown-menu><el-dropdown-item :icon="EditPen" @click="editTodo(todo)">编辑</el-dropdown-item><el-dropdown-item :icon="Delete" @click="removeTodo(todo.id)">删除</el-dropdown-item></el-dropdown-menu></template>
                  </el-dropdown>
                </div>
              </div>
              <div class="todo-empty" v-else><span><el-icon><CircleCheck /></el-icon></span><strong>这一天还没有待办</strong><p>添加一项计划，让每一步都更从容。</p></div>
            </template>
            <div class="todo-form">
              <el-input v-model="todoInput" placeholder="添加新的待办事项...（按 Enter 快速添加）" aria-label="待办内容" maxlength="80" @keyup.enter="addTodo" />
              <div class="todo-form-bottom"><div class="priority-picker"><span>优先级</span><el-select v-model="todoPriority" size="small" aria-label="优先级" style="width: 92px"><el-option label="普通" value="normal"><span class="priority-option"><i class="priority-dot normal" />普通</span></el-option><el-option label="重要" value="high"><span class="priority-option"><i class="priority-dot high" />重要</span></el-option><el-option label="低" value="low"><span class="priority-option"><i class="priority-dot low" />低</span></el-option></el-select></div><el-button type="primary" :disabled="todoBusy || todoLoading" :icon="Plus" @click="addTodo">添加</el-button></div>
            </div>
            <div class="todo-actions"><button type="button" :disabled="todoBusy || todoLoading || !!todoError || !pendingCount" @click="completeAll"><el-icon><Check /></el-icon>全部完成</button><button type="button" :disabled="todoBusy || todoLoading || !!todoError || !completedCount" @click="clearCompleted"><el-icon><Delete /></el-icon>清除已完成</button></div>
          </section>
        </div>

        <div class="bottom-note"><span><el-icon><MagicStick /></el-icon></span> 让 AI 承担重复工作，把更多时间留给每一个好奇的孩子。<em>科学课堂，从这里开始。</em></div>
      </main>
    </div>

    <el-dialog v-model="mobileSearchOpen" title="搜索功能或向 AI 提问" width="min(90vw, 420px)" @opened="searchInput?.focus()"><el-input ref="searchInput" v-model="searchValue" maxlength="4000" placeholder="输入功能名称，或将问题带入 AI 对话" clearable @keyup.enter="submitSearch" /><template #footer><el-button @click="mobileSearchOpen = false">取消</el-button><el-button type="primary" @click="submitSearch">继续</el-button></template></el-dialog>
  </div>
  <div v-else class="workbench-entry">
    <p v-if="restoringSession" role="status">正在验证登录状态…</p>
  </div>
  <el-dialog
    :model-value="!restoringSession && !todoTeacher"
    title="教师登录"
    width="min(420px, calc(100vw - 32px))"
    align-center
    destroy-on-close
    :show-close="false"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    @opened="loginPassword?.focus()"
  >
    <form class="workbench-login" @submit.prevent="loginTodos">
      <p>登录小学科学 AI 教师工作台</p>
      <label for="workbench-username">用户名</label>
      <el-input id="workbench-username" v-model="todoCredentials.username" name="username" autocomplete="username" maxlength="64" :disabled="signingIn" required>
        <template #prefix><el-icon><User /></el-icon></template>
      </el-input>
      <label for="workbench-password">密码</label>
      <el-input id="workbench-password" ref="loginPassword" v-model="todoCredentials.password" name="password" type="password" autocomplete="current-password" maxlength="128" :disabled="signingIn" required>
        <template #prefix><el-icon><Lock /></el-icon></template>
      </el-input>
      <p v-if="loginError" class="workbench-login-error" role="alert">{{ loginError }}</p>
      <el-button class="workbench-login-submit" native-type="submit" type="primary" :loading="signingIn">登录</el-button>
    </form>
  </el-dialog>
</template>

<style scoped>
.workspace-chevron { margin-left: auto; }
.workspace-group[aria-expanded="true"] .workspace-chevron { transform: rotate(180deg); }
.workspace-child small { margin-left: 6px; font-size: 10px; opacity: .72; }
.app-shell:not(.sidebar-collapsed) .workspace-child { padding-left: 30px; }
.slot-prep-link {
  display: block;
  max-width: 100%;
  margin: 3px auto 0;
  padding: 1px 4px;
  overflow: hidden;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--el-color-primary);
  font: inherit;
  font-size: 11px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}
.slot-prep-link:hover { text-decoration: underline; }
.slot-prep-link:focus-visible { outline: 2px solid currentColor; }
.todo-import { display: flex; align-items: center; flex-wrap: wrap; justify-content: space-between; gap: 5px; margin-bottom: 10px; font-size: 12px; color: #52645c; }
.workbench-entry { min-height: 100vh; display: grid; place-items: center; color: var(--el-text-color-secondary); }
.workbench-login { display: grid; gap: 8px; }
.workbench-login p { margin: 0 0 8px; color: var(--el-text-color-secondary); }
.workbench-login label { margin-top: 4px; color: var(--el-text-color-primary); font-weight: 600; }
.workbench-login .workbench-login-error { margin: 4px 0 0; color: var(--el-color-danger); }
.workbench-login-submit { width: 100%; margin-top: 10px; }
</style>
