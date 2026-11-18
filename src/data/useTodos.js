import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiMessage, todoApi } from './todoApi'

const tokenKey = 'science-workbench-session-v1'
const legacyKey = 'science-workbench-demo-todos-v1'
const priorities = ['normal', 'high', 'low']

function readLegacy() {
  try {
    const saved = JSON.parse(localStorage.getItem(legacyKey))
    if (!Array.isArray(saved)) return []
    return saved.flatMap(item => {
      if (!item || !['number', 'string'].includes(typeof item.id) || typeof item.content !== 'string') return []
      const content = item.content.trim()
      if (!content || content.length > 80 || !/^\d{4}-\d{2}-\d{2}$/.test(item.date)) return []
      const parsed = new Date(item.date)
      if (!Number.isFinite(+parsed) || parsed.toISOString().slice(0, 10) !== item.date || item.date.startsWith('0000-')) return []
      const legacy_key = item.date + ':' + item.id
      if (legacy_key.length > 128) return []
      return [{ legacy_key, date: item.date, content, done: item.done === true, priority: priorities.includes(item.priority) ? item.priority : 'normal' }]
    })
  } catch { return [] }
}

export function useTodos(selectedDate, today) {
  const teacher = ref(null)
  const credentials = reactive({ username: 'teacher', password: '' })
  const loginError = ref('')
  const listError = ref('')
  const loading = ref(false)
  const signingIn = ref(false)
  const restoringSession = ref(true)
  const busy = ref(false)
  const records = ref({})
  const todoInput = ref('')
  const todoPriority = ref('normal')
  const legacy = readLegacy()
  const importAcknowledged = ref(false)
  const importedMarker = () => legacyKey + ':imported:' + teacher.value?.id + ':' + teacher.value?.username
  let token = ''
  let requestId = 0

  const visibleTodos = computed(() => records.value[selectedDate.value] || [])
  const todayPendingCount = computed(() => records.value[today.value]?.filter(item => !item.done).length ?? null)
  const completedCount = computed(() => visibleTodos.value.filter(item => item.done).length)
  const pendingCount = computed(() => visibleTodos.value.length - completedCount.value)
  const progress = computed(() => visibleTodos.value.length ? Math.round(completedCount.value / visibleTodos.value.length * 100) : 0)

  function logout() {
    ++requestId
    token = ''
    teacher.value = null
    records.value = {}
    credentials.password = ''
    loginError.value = ''
    listError.value = ''
    loading.value = false
    todoInput.value = ''
    todoPriority.value = 'normal'
    try { sessionStorage.removeItem(tokenKey) } catch { /* session remains in memory */ }
  }

  function adoptAccount(user) {
    teacher.value = user
    try { importAcknowledged.value = localStorage.getItem(importedMarker()) === '1' }
    catch { importAcknowledged.value = false }
  }

  function sessionExpired(error, requestToken) {
    if (error.response?.status !== 401 || token !== requestToken) return false
    logout()
    loginError.value = '登录已失效，请重新登录。'
    return true
  }

  async function refresh() {
    if (!teacher.value) return
    const current = ++requestId
    const requestToken = token
    const dates = [...new Set([selectedDate.value, today.value])]
    loading.value = true
    listError.value = ''
    try {
      const rows = await Promise.all(dates.map(date => todoApi.list(requestToken, date)))
      if (current === requestId) records.value = Object.fromEntries(dates.map((date, i) => [date, rows[i]]))
    } catch (error) {
      if (current === requestId && !sessionExpired(error, requestToken)) listError.value = apiMessage(error)
    } finally {
      if (current === requestId) loading.value = false
    }
  }

  onMounted(async () => {
    try { token = sessionStorage.getItem(tokenKey) || '' } catch { /* browser storage unavailable */ }
    try {
      if (token) adoptAccount(await todoApi.me(token))
    } catch (error) {
      if (!sessionExpired(error, token)) loginError.value = apiMessage(error)
    } finally { restoringSession.value = false }
  })

  watch([selectedDate, today, teacher], refresh)

  async function login() {
    if (signingIn.value || !credentials.username.trim() || !credentials.password) return
    signingIn.value = true
    loginError.value = ''
    try {
      const result = await todoApi.login({ username: credentials.username, password: credentials.password })
      token = result.access_token
      try { sessionStorage.setItem(tokenKey, token) } catch { /* session remains in memory */ }
      adoptAccount(result.user)
    } catch (error) { loginError.value = apiMessage(error) }
    finally {
      credentials.password = ''
      signingIn.value = false
    }
  }

  async function mutate(operation, success) {
    if (!teacher.value || busy.value) return false
    const requestToken = token
    busy.value = true
    try {
      const result = await operation(requestToken)
      if (success) ElMessage.success(typeof success === 'function' ? success(result) : success)
      await refresh()
      return true
    } catch (error) {
      if (!sessionExpired(error, requestToken)) ElMessage.error(apiMessage(error))
      return false
    } finally { busy.value = false }
  }

  async function addTodo() {
    const content = todoInput.value.trim()
    if (!content) return ElMessage.warning('请输入待办内容')
    const data = { content, priority: todoPriority.value, date: selectedDate.value }
    if (await mutate(auth => todoApi.create(auth, data), '已添加待办')) {
      if (todoInput.value.trim() === content) todoInput.value = ''
      todoPriority.value = 'normal'
    }
  }

  async function editTodo(todo) {
    if (busy.value) return
    let result
    try {
      result = await ElMessageBox.prompt('修改待办内容', '编辑待办', {
        inputValue: todo.content, inputValidator: value => (value?.trim().length > 0 && value.trim().length <= 80) || '请输入 1–80 个字符',
        confirmButtonText: '保存', cancelButtonText: '取消',
      })
    } catch { return }
    await mutate(auth => todoApi.update(auth, todo.id, { content: result.value.trim() }), '已保存')
  }

  async function importLegacy() {
    if (busy.value || !legacy.length) return
    try {
      await ElMessageBox.confirm('将本浏览器里的旧待办导入当前教师账号，原记录会保留。', '导入旧待办', {
        confirmButtonText: '导入', cancelButtonText: '取消',
      })
    } catch { return }
    const ok = await mutate(async auth => {
      let imported = 0
      for (let offset = 0; offset < legacy.length; offset += 500) {
        imported += (await todoApi.import(auth, legacy.slice(offset, offset + 500))).imported
      }
      return imported
    }, count => '已导入 ' + count + ' 项待办')
    if (!ok) return
    importAcknowledged.value = true
    try { localStorage.setItem(importedMarker(), '1') } catch { /* the server deduplicates repeat imports */ }
  }

  return {
    getChatToken: () => token,
    teacher, credentials, restoringSession, signingIn, loginError, listError, loading, busy, refresh, login, logout,
    todoInput, todoPriority, todayPendingCount, visibleTodos, completedCount, pendingCount, progress,
    legacyCount: computed(() => importAcknowledged.value ? 0 : legacy.length), importLegacy,
    addTodo, editTodo,
    toggleTodo: (todo, done) => mutate(auth => todoApi.update(auth, todo.id, { done })),
    removeTodo: id => mutate(auth => todoApi.remove(auth, id), '已删除'),
    completeAll: () => mutate(auth => todoApi.complete(auth, selectedDate.value), '当天待办已全部完成'),
    clearCompleted: () => mutate(auth => todoApi.clearCompleted(auth, selectedDate.value), result => '已清除 ' + result.deleted + ' 项已完成待办'),
  }
}
