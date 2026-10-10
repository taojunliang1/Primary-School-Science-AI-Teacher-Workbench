<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Aim, ArrowDown, ArrowLeft, ArrowRight, Bell, Calendar, ChatDotRound,
  Check, CircleCheck, Collection, Compass, Connection, Cpu, DataAnalysis, Delete, Document,
  EditPen, Expand, Fold, HomeFilled, List, MagicStick, Menu, MoreFilled,
  Notebook, Plus, Reading, Search, Setting, Trophy, User,
  VideoPlay, View,
} from '@element-plus/icons-vue'
import { timetableDays, timetableRows } from './data/timetable'
import SlidesWorkspace from './components/SlidesWorkspace.vue'
import TeachingPrepWorkspace from './components/TeachingPrepWorkspace.vue'

const now = new Date()
const teacherName = '张老师'
const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
const pad = (value) => String(value).padStart(2, '0')
const dateKey = (date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
const parseDate = (value) => {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day)
}
const todayKey = dateKey(now)
const selectedDate = ref(todayKey)
const formattedToday = computed(() => `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日 ${weekdays[now.getDay()]}`)
const selectedDateObject = computed(() => parseDate(selectedDate.value))
const selectedDateLabel = computed(() => `${selectedDateObject.value.getMonth() + 1}月${selectedDateObject.value.getDate()}日`)
const selectedWeekday = computed(() => weekdays[selectedDateObject.value.getDay()])
const isToday = computed(() => selectedDate.value === todayKey)
const todayColumn = now.getDay() - 1
const todayCourseCount = computed(() => timetableRows.filter((row) => !row.band && row.slots?.[todayColumn]?.isClass).length)

const navigation = [
  { label: '工作台首页', icon: HomeFilled, key: 'home' },
  { group: '教学筹备', items: [
    { label: '科学课件生成', icon: Document, key: 'slides' },
    { label: '科学探究设计', icon: Compass, key: 'inquiry' },
    { label: '教学案例', icon: VideoPlay, key: 'cases' },
    { label: '教研论文', icon: Reading, key: 'papers' },
    { label: '心得体会', icon: Notebook, key: 'reflections' },
  ] },
  { group: '教学管理', items: [
    { label: '班级管理', icon: User, key: 'classes' },
    { label: '实验报告批改', icon: View, key: 'reports' },
    { label: '课后复盘', icon: Collection, key: 'review' },
  ] },
  { group: '科学创作', items: [
    { label: '科学示意图生成', icon: Connection, key: 'images' },
    { label: '虚拟实验库', icon: Cpu, key: 'experiments' },
    { label: '教学视频生成', icon: VideoPlay, key: 'videos' },
  ] },
  { group: '智能助手', items: [
    { label: '实验数据分析', icon: DataAnalysis, key: 'analysis' },
    { label: '公式 / 器材识别', icon: Search, key: 'recognition' },
    { label: 'AI 对话', icon: ChatDotRound, key: 'chat' },
  ] },
  { group: '作品与荣誉', items: [
    { label: '科技创新大赛', icon: Trophy, key: 'competition' },
    { label: '作品集锦', icon: Collection, key: 'works' },
  ] },
]

const featured = [
  { title: '科学课件生成', subtitle: '让知识变得生动可见', icon: Document, color: 'gold', key: 'slides' },
  { title: '虚拟实验设计', subtitle: '把实验带进每间教室', icon: Cpu, color: 'rose', key: 'experiments' },
  { title: '科学教学案例', subtitle: '从真实课堂汲取灵感', icon: Reading, color: 'violet', key: 'cases' },
  { title: '科学绘图', subtitle: '一键呈现科学概念', icon: Connection, color: 'pink', key: 'images' },
]
const secondary = [
  { title: '教研论文', icon: Reading, color: 'teal', key: 'papers' },
  { title: '心得体会', icon: Notebook, color: 'mint', key: 'reflections' },
  { title: '班级管理', icon: User, color: 'blue', key: 'classes' },
  { title: '数据分析', icon: DataAnalysis, color: 'cyan', key: 'analysis' },
  { title: '每日待办', icon: List, color: 'orange', key: 'todos' },
  { title: 'AI 对话', icon: ChatDotRound, color: 'lavender', key: 'chat' },
]

const sidebarCollapsed = ref(false)
const prepPages = ['slides', 'inquiry', 'cases', 'papers', 'reflections']
const pageFromHash = () => {
  const key = window.location.hash.slice(1)
  return prepPages.includes(key) ? key : 'home'
}
const activePage = ref(pageFromHash())
const mobileSidebarOpen = ref(false)
const mobileSearchOpen = ref(false)
const searchValue = ref('')
const todoInput = ref('')
const todoPriority = ref('normal')
const taskPopoverOpen = ref(false)
const expandedGroups = ref(Object.fromEntries(navigation.filter((entry) => entry.group).map((entry) => [entry.group, true])))
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
  if (key === 'home') {
    activePage.value = 'home'
    window.location.hash = 'home'
    nextTick(() => window.scrollTo({ top: 0, behavior: 'smooth' }))
    return
  }
  if (prepPages.includes(key)) {
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

function syncPageFromHash() {
  activePage.value = pageFromHash()
}
onMounted(() => window.addEventListener('hashchange', syncPageFromHash))
onUnmounted(() => window.removeEventListener('hashchange', syncPageFromHash))

function submitSearch() {
  const query = searchValue.value.trim().toLowerCase()
  if (!query) return
  const all = navigation.flatMap((entry) => entry.items || [entry])
  const match = all.find((item) => item.label.toLowerCase().includes(query))
  if (match) openFeature(match.key, match.label)
  else ElMessage({ message: '没有找到匹配的功能，请试试“课件”“实验”或“待办”。', type: 'warning' })
  searchValue.value = ''
  mobileSearchOpen.value = false
}

const storageKey = 'science-workbench-demo-todos-v1'
const starterTodos = [
  { id: 1, date: todayKey, content: '完善四年级《蚕》的实验材料清单', priority: 'high', done: false },
  { id: 2, date: todayKey, content: '批改四（25）班实验观察记录', priority: 'normal', done: false },
  { id: 3, date: todayKey, content: '整理本周科学探究活动照片', priority: 'low', done: true },
]
let savedTodos
try {
  savedTodos = JSON.parse(localStorage.getItem(storageKey))
} catch {
  savedTodos = null
}
const todos = ref(Array.isArray(savedTodos) ? savedTodos : starterTodos)
watch(todos, (value) => localStorage.setItem(storageKey, JSON.stringify(value)), { deep: true })
const todayPendingCount = computed(() => todos.value.filter((item) => item.date === todayKey && !item.done).length)
const visibleTodos = computed(() => todos.value.filter((item) => item.date === selectedDate.value))
const completedCount = computed(() => visibleTodos.value.filter((item) => item.done).length)
const pendingCount = computed(() => visibleTodos.value.length - completedCount.value)
const progress = computed(() => visibleTodos.value.length ? Math.round(completedCount.value / visibleTodos.value.length * 100) : 0)

function moveDate(offset) {
  const target = parseDate(selectedDate.value)
  target.setDate(target.getDate() + offset)
  selectedDate.value = dateKey(target)
}

function addTodo() {
  const content = todoInput.value.trim()
  if (!content) return ElMessage.warning('请先填写待办内容')
  todos.value.unshift({ id: Date.now(), date: selectedDate.value, content, priority: todoPriority.value, done: false })
  todoInput.value = ''
  todoPriority.value = 'normal'
  ElMessage.success('已添加到当天待办')
}

async function editTodo(todo) {
  try {
    const { value } = await ElMessageBox.prompt('修改待办内容', '编辑待办', {
      inputValue: todo.content,
      inputValidator: (value) => Boolean(value?.trim()) || '待办内容不能为空',
      confirmButtonText: '保存',
      cancelButtonText: '取消',
    })
    todo.content = value.trim()
    ElMessage.success('已保存')
  } catch {
    // 用户取消编辑。
  }
}

function removeTodo(id) {
  todos.value = todos.value.filter((item) => item.id !== id)
  ElMessage.success('已删除')
}

function completeAll() {
  visibleTodos.value.forEach((item) => { item.done = true })
  ElMessage.success('当天待办已全部完成')
}

function clearCompleted() {
  const count = completedCount.value
  todos.value = todos.value.filter((item) => item.date !== selectedDate.value || !item.done)
  ElMessage.success(`已清除 ${count} 项已完成待办`)
}
</script>

<template>
  <div class="app-shell" :class="{ 'sidebar-collapsed': sidebarCollapsed, 'mobile-nav-open': mobileSidebarOpen }">
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
              <button v-if="!sidebarCollapsed" class="nav-group-title" type="button" :aria-expanded="expandedGroups[entry.group]" @click="expandedGroups[entry.group] = !expandedGroups[entry.group]">{{ entry.group }}<el-icon :class="{ closed: !expandedGroups[entry.group] }"><ArrowDown /></el-icon></button>
              <button v-for="item in (sidebarCollapsed || expandedGroups[entry.group] ? entry.items : [])" :key="item.key" class="nav-link" :class="{ selected: activePage === item.key }" type="button" @click="openFeature(item.key, item.label)" :title="item.label">
                <el-icon><component :is="item.icon" /></el-icon><span v-if="!sidebarCollapsed">{{ item.label }}</span>
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
          <div class="search-box"><el-icon><Search /></el-icon><input v-model="searchValue" placeholder="搜索功能..." aria-label="搜索功能" @keyup.enter="submitSearch" /><kbd>↵</kbd></div>
          <button class="mobile-search icon-button" type="button" aria-label="搜索功能" @click="mobileSearchOpen = true"><el-icon><Search /></el-icon></button>
          <el-popover v-model:visible="taskPopoverOpen" placement="bottom-end" :width="286" trigger="click">
            <template #reference><button class="task-status" type="button"><span class="task-pulse idle" /> <span>0 个生成中</span></button></template>
            <div class="popover-task"><div class="popover-title">AI 任务中心</div><p>当前没有生成任务。AI 课件功能将在后续阶段接入。</p></div>
          </el-popover>
          <el-tooltip content="通知中心将在后续阶段开放" placement="bottom"><button class="icon-button notification-btn" type="button" @click="openFeature('notifications', '通知中心')"><el-icon><Bell /></el-icon><i /></button></el-tooltip>
          <el-dropdown trigger="click">
            <button class="user-trigger" type="button"><span class="avatar">鹤</span><span class="user-name">{{ teacherName }}</span><el-icon><ArrowDown /></el-icon></button>
            <template #dropdown><el-dropdown-menu><el-dropdown-item :icon="User" @click="openFeature('profile', '个人资料')">个人资料</el-dropdown-item><el-dropdown-item :icon="Aim" @click="toggleTheme">{{ theme === 'science' ? '切换至原配色' : '切换至青绿主题' }}</el-dropdown-item><el-dropdown-item :icon="Setting" @click="openFeature('settings', '系统设置')">系统设置</el-dropdown-item></el-dropdown-menu></template>
          </el-dropdown>
        </div>
      </header>

      <SlidesWorkspace v-if="activePage === 'slides'" @back="openFeature('home', '工作台首页')" />
      <TeachingPrepWorkspace v-else-if="prepPages.includes(activePage)" :key="activePage" :mode="activePage" @back="openFeature('home', '工作台首页')" @navigate="(key) => openFeature(key, key)" />
      <main v-else class="dashboard">
        <section class="welcome-banner" aria-label="今日欢迎">
          <div class="welcome-content"><div class="welcome-eyebrow"><span class="eyebrow-dot" />{{ now.getMonth() + 1 }}月{{ now.getDate() }}日 · 今日科学</div><h1>欢迎{{ teacherName }}，美好的一天从探索开始</h1><p>今天有 <strong>{{ todayCourseCount }} 节科学课</strong>，<strong>{{ todayPendingCount }} 项任务</strong>待办。<span class="ai-tip">让 AI 帮你搞定实验设计</span>，省出时间专注科学思维培养 <span class="banner-star">✦</span></p></div>
          <div class="banner-art" aria-hidden="true"><div class="orbit orbit-one"/><div class="orbit orbit-two"/><div class="planet planet-one"/><div class="planet planet-two"/><div class="planet planet-three"/><span class="sparkle sparkle-one">✧</span><span class="sparkle sparkle-two">✦</span><span class="sparkle sparkle-three">✧</span></div>
        </section>

        <section class="quick-card surface-card" aria-labelledby="quick-title">
          <div class="section-heading"><div><span class="overline">EXPLORE & CREATE</span><h2 id="quick-title">快捷入口</h2></div><span class="section-caption">从灵感出发，开启今天的科学课堂</span></div>
          <div class="featured-grid"><button v-for="item in featured" :key="item.key" class="featured-entry" type="button" @click="openFeature(item.key, item.title)"><span class="featured-icon" :class="item.color"><el-icon><component :is="item.icon" /></el-icon></span><strong>{{ item.title }}</strong><small>{{ item.subtitle }}</small><el-icon class="entry-arrow"><ArrowRight /></el-icon></button></div>
          <div class="quick-divider" />
          <div class="secondary-grid"><button v-for="item in secondary" :key="item.key" class="secondary-entry" type="button" @click="openFeature(item.key, item.title)"><span class="secondary-icon" :class="item.color"><el-icon><component :is="item.icon" /></el-icon></span><span>{{ item.title }}</span></button></div>
        </section>

        <div class="content-grid">
          <section class="course-card surface-card" aria-labelledby="course-title">
            <div class="card-header"><div class="card-title-wrap"><span class="heading-icon rose"><el-icon><Calendar /></el-icon></span><div><span class="overline">WEEKLY TIMETABLE</span><h2 id="course-title">今日课程 · 本周课表</h2></div></div><span class="schedule-week-label">{{ formattedToday }}</span></div>
            <div class="timetable-scroll" role="region" aria-label="本周课程表，可横向滚动" tabindex="0">
              <div class="timetable-inner">
              <table class="timetable">
                <thead><tr><th colspan="2" scope="col">时间</th><th v-for="(day, index) in timetableDays" :key="day" scope="col" :class="{ 'today-column': index === todayColumn }">{{ day }}<span v-if="index === todayColumn" class="day-today-dot" aria-label="今天" /></th></tr></thead>
                <tbody>
                  <tr v-for="row in timetableRows" :key="row.time" :class="`row-${row.band || 'regular'}`">
                    <th v-if="row.section" class="section-time" scope="row" :rowspan="row.sectionRowspan || 1">{{ row.section }}</th>
                    <th class="clock-time" scope="row" :colspan="row.section || row.sectionContinue ? 1 : 2">{{ row.time }}</th>
                    <td v-if="row.merged" class="merged-event" colspan="5">{{ row.merged }}</td>
                    <template v-else v-for="(slot, dayIndex) in row.slots" :key="dayIndex">
                      <td v-if="!slot.skip" :rowspan="slot.rowSpan || 1" :class="['schedule-slot', { 'today-column': dayIndex === todayColumn, 'research-slot': slot.type === 'research' }]">
                        <span v-if="slot.text" :class="['slot-label', { 'important-lesson': slot.important, 'event-label': slot.isClass === false }]">{{ slot.text }}</span>
                      </td>
                    </template>
                  </tr>
                </tbody>
              </table>
              <div v-if="todayColumn >= 0 && todayColumn < 5" class="today-column-outline" :style="{ gridColumn: `${todayColumn + 2} / span 1` }" aria-hidden="true" />
              </div>
            </div>
            <div class="timetable-legend"><span><i class="legend-dot key-lesson" />标记课次</span><span><i class="legend-dot today-day" />今天</span><span class="legend-note">课表为样例数据，暂未接入数据库</span></div>
          </section>

          <section id="todo-card" class="todo-card surface-card" aria-labelledby="todo-title">
            <div class="card-header"><div class="card-title-wrap"><span class="heading-icon peach"><el-icon><List /></el-icon></span><div><span class="overline">DAILY PLANNER</span><h2 id="todo-title">每日待办</h2></div></div><span class="pending-pill">{{ pendingCount }} 项待办</span></div>
            <div class="date-switcher"><button type="button" aria-label="前一天" @click="moveDate(-1)"><el-icon><ArrowLeft /></el-icon></button><div><el-icon><Calendar /></el-icon><strong>{{ selectedDateLabel }}</strong><span>{{ selectedWeekday }}</span><span v-if="isToday" class="today-marker">今天</span></div><button type="button" aria-label="后一天" @click="moveDate(1)"><el-icon><ArrowRight /></el-icon></button></div>
            <div class="todo-stats"><span>共 <strong>{{ visibleTodos.length }}</strong> 项 · 已完成 <strong>{{ completedCount }}</strong> · 未完成 <strong>{{ pendingCount }}</strong></span><span><strong>{{ progress }}%</strong></span></div><el-progress :percentage="progress" :show-text="false" :stroke-width="5" :color="theme === 'science' ? '#10B981' : '#a87b89'" />
            <div class="todo-list" v-if="visibleTodos.length"><div v-for="todo in visibleTodos" :key="todo.id" class="todo-row" :class="{ done: todo.done }"><el-checkbox v-model="todo.done" :aria-label="`完成${todo.content}`" /><span class="todo-text" @dblclick="editTodo(todo)">{{ todo.content }}</span><el-tag v-if="todo.priority !== 'normal'" :type="todo.priority === 'high' ? 'danger' : 'info'" size="small" effect="plain" round>{{ todo.priority === 'high' ? '重要' : '低' }}</el-tag><el-dropdown trigger="click"><button class="todo-more" type="button" aria-label="更多待办操作"><el-icon><MoreFilled /></el-icon></button><template #dropdown><el-dropdown-menu><el-dropdown-item :icon="EditPen" @click="editTodo(todo)">编辑</el-dropdown-item><el-dropdown-item :icon="Delete" @click="removeTodo(todo.id)">删除</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div></div>
            <div class="todo-empty" v-else><span><el-icon><CircleCheck /></el-icon></span><strong>今天还没有待办</strong><p>添加一项计划，让每一步都更从容。</p></div>
            <div class="todo-form"><el-input v-model="todoInput" placeholder="添加新的待办事项...（按 Enter 快速添加）" maxlength="80" @keyup.enter="addTodo" /><div class="todo-form-bottom"><div class="priority-picker"><span>优先级</span><el-select v-model="todoPriority" size="small" style="width: 92px"><el-option label="普通" value="normal"><span class="priority-option"><i class="priority-dot normal" />普通</span></el-option><el-option label="重要" value="high"><span class="priority-option"><i class="priority-dot high" />重要</span></el-option><el-option label="低" value="low"><span class="priority-option"><i class="priority-dot low" />低</span></el-option></el-select></div><el-button type="primary" :icon="Plus" @click="addTodo">添加</el-button></div></div>
            <div class="todo-actions"><button type="button" :disabled="!pendingCount" @click="completeAll"><el-icon><Check /></el-icon>全部完成</button><button type="button" :disabled="!completedCount" @click="clearCompleted"><el-icon><Delete /></el-icon>清除已完成</button></div>
          </section>
        </div>

        <div class="bottom-note"><span><el-icon><MagicStick /></el-icon></span> 让 AI 承担重复工作，把更多时间留给每一个好奇的孩子。<em>科学课堂，从这里开始。</em></div>
      </main>
    </div>

    <el-dialog v-model="mobileSearchOpen" title="搜索功能" width="min(90vw, 420px)"><el-input v-model="searchValue" placeholder="输入课件、实验、待办等关键词" clearable @keyup.enter="submitSearch"><template #prefix><el-icon><Search /></el-icon></template></el-input><template #footer><el-button @click="mobileSearchOpen = false">取消</el-button><el-button type="primary" @click="submitSearch">搜索</el-button></template></el-dialog>
  </div>
</template>
