<script setup>
import { computed, onBeforeUnmount, reactive, ref, shallowRef, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowRight, Delete, Document, Download, EditPen, Notebook, Plus, Reading, Search } from '@element-plus/icons-vue'
import { Editor, Toolbar } from '@wangeditor/editor-for-vue'
import DOMPurify from 'dompurify'
import '@wangeditor/editor/dist/css/style.css'
import { gradeOptions, preparationModes } from '../data/teachingPrep'

const props = defineProps({ mode: { type: String, required: true } })
const emit = defineEmits(['back'])
const config = preparationModes[props.mode]
const icon = { cases: Document, papers: Reading, reflections: Notebook }[props.mode]
const categories = {
  cases: ['课堂探究', '实验教学', '跨学科', '其他'],
  papers: ['写作中', '待修改', '已完成'],
  reflections: ['课堂亮点', '问题复盘', '改进计划'],
}[props.mode]
const storageKey = `science-workbench-prep-${props.mode}-v1`
const workingKey = `${storageKey}-working`
const todayKey = () => {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}
const safeHtml = (html) => DOMPurify.sanitize(html || '', { USE_PROFILES: { html: true } })
const plainText = (html) => new DOMParser().parseFromString(safeHtml(html), 'text/html').body.textContent?.trim() || ''

function blankDraft() {
  const data = Object.fromEntries([...config.fields, ...config.sections].map((field) => [field.key, '']))
  if (props.mode === 'reflections') data.date = todayKey()
  return { ...data, category: '', bodyHtml: '' }
}
function normalizedDraft(source) {
  const data = blankDraft()
  for (const key of Object.keys(data)) if (typeof source?.[key] === 'string') data[key] = source[key]
  data.bodyHtml = plainText(data.bodyHtml) ? safeHtml(data.bodyHtml) : ''
  return data
}
function normalizedBaseline(value) {
  try { return JSON.stringify(normalizedDraft(JSON.parse(value))) }
  catch { return JSON.stringify(blankDraft()) }
}
function readRecords() {
  try {
    const data = JSON.parse(localStorage.getItem(storageKey) || '[]')
    return Array.isArray(data) ? data.filter((item) => item && typeof item.id === 'string' && typeof item.data?.title === 'string') : []
  } catch { return [] }
}
const records = ref(readRecords())
let working = null
try { working = JSON.parse(localStorage.getItem(workingKey) || 'null') } catch { /* 无可恢复草稿 */ }
const hasWorking = ref(Boolean(working?.data && JSON.stringify(normalizedDraft(working.data)) !== normalizedBaseline(working.baseline)))
const query = ref('')
const categoryFilter = ref('')
const drawerOpen = ref(false)
const editing = ref(false)
const selectedId = ref(null)
const isExample = ref(false)
const draft = reactive(blankDraft())
const baseline = ref(JSON.stringify(blankDraft()))
const editorRef = shallowRef(null)
const editorConfig = { placeholder: '记录完整的教学过程、证据与思考……', MENU_CONF: { uploadImage: { customUpload: () => ElMessage.info('图片上传将在接入文件存储后开放') } } }
const toolbarConfig = { excludeKeys: ['uploadImage', 'uploadVideo', 'insertImage', 'insertVideo', 'fullScreen'] }
const isDirty = computed(() => editing.value && JSON.stringify(normalizedDraft(draft)) !== baseline.value)
const allItems = computed(() => [
  ...records.value.map((record) => ({ ...record, example: false })),
  ...config.examples.map((example, index) => ({ id: `example-${index}`, data: example.data, updatedAt: '', example: true, tag: example.tag })),
])
const filteredItems = computed(() => {
  const needle = query.value.trim().toLowerCase()
  return allItems.value.filter((item) => {
    const data = item.data
    const matchesCategory = !categoryFilter.value || (data.category || '未分类') === categoryFilter.value
    const searchText = [data.title, data.topic, data.keywords, ...config.sections.map((section) => data[section.key])].join(' ').toLowerCase()
    return matchesCategory && (!needle || searchText.includes(needle))
  })
})
const excerpt = (item) => {
  const data = item.data
  const text = plainText(data.bodyHtml) || config.sections.map((section) => data[section.key]).find(Boolean) || '打开查看详情'
  return text.length > 105 ? `${text.slice(0, 105)}…` : text
}
const currentLabel = computed(() => isExample.value ? '演示素材' : selectedId.value ? '我的记录' : '新建记录')

watch(draft, () => {
  if (!editing.value) return
  try {
    localStorage.setItem(workingKey, JSON.stringify({ data: normalizedDraft(draft), selectedId: selectedId.value, baseline: baseline.value }))
    hasWorking.value = isDirty.value
  } catch { /* 保存时会显示本地存储错误 */ }
}, { deep: true })
onBeforeUnmount(() => editorRef.value?.destroy())
function onEditorCreated(editor) { editorRef.value = editor }
function setDraft(data) {
  Object.assign(draft, normalizedDraft(data))
  baseline.value = JSON.stringify(normalizedDraft(draft))
}
async function confirmDiscard() {
  if (!isDirty.value) return true
  try {
    await ElMessageBox.confirm('当前修改尚未保存，确定放弃吗？', '未保存的修改', { type: 'warning', confirmButtonText: '放弃修改', cancelButtonText: '继续编辑' })
    return true
  } catch { return false }
}
async function openItem(item) {
  if (!await confirmDiscard()) return
  selectedId.value = item.example ? null : item.id
  isExample.value = item.example
  editing.value = false
  setDraft(item.data)
  drawerOpen.value = true
}
async function startNew(source = null) {
  if (!await confirmDiscard()) return
  selectedId.value = null
  isExample.value = false
  editing.value = false
  setDraft(source || blankDraft())
  editing.value = true
  drawerOpen.value = true
}
function resumeDraft() {
  if (!working?.data) return
  selectedId.value = records.value.some((record) => record.id === working.selectedId) ? working.selectedId : null
  isExample.value = false
  editing.value = false
  setDraft(working.data)
  baseline.value = normalizedBaseline(working.baseline)
  editing.value = true
  drawerOpen.value = true
  hasWorking.value = false
}
async function requestClose(done) {
  if (!await confirmDiscard()) return
  editing.value = false
  drawerOpen.value = false
  done?.()
}
function beginEdit() {
  if (isExample.value) return startNew(draft)
  editing.value = true
}
function saveRecord() {
  if (!draft.title.trim()) return ElMessage.warning(`请先填写${config.fields[0].label}`)
  const hasContent = plainText(draft.bodyHtml) || config.sections.some((section) => draft[section.key]?.trim())
  if (!hasContent) return ElMessage.warning('请填写正文或至少一个原有分段内容')
  const id = selectedId.value || `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  const updatedAt = new Date().toLocaleString('zh-CN', { hour12: false })
  const data = normalizedDraft(draft)
  const next = [{ id, updatedAt, data }, ...records.value.filter((item) => item.id !== id)]
  try {
    localStorage.setItem(storageKey, JSON.stringify(next))
    localStorage.removeItem(workingKey)
  } catch { return ElMessage.error('保存失败，请检查浏览器本地存储空间') }
  records.value = next
  selectedId.value = id
  baseline.value = JSON.stringify(data)
  editing.value = false
  hasWorking.value = false
  working = null
  ElMessage.success(`${config.itemName}已保存到当前浏览器`)
}
async function deleteRecord(item) {
  try {
    await ElMessageBox.confirm(`确定删除“${item.data.title}”吗？`, '删除记录', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch { return }
  const next = records.value.filter((record) => record.id !== item.id)
  try { localStorage.setItem(storageKey, JSON.stringify(next)) } catch { return ElMessage.error('删除失败，请检查浏览器本地存储空间') }
  records.value = next
  if (selectedId.value === item.id) { editing.value = false; drawerOpen.value = false }
  ElMessage.success('记录已删除')
}
function exportMarkdown() {
  const metadata = config.fields.filter((field) => field.key !== 'title' && draft[field.key]?.trim()).map((field) => `- **${field.label}：** ${draft[field.key].trim()}`)
  const legacy = config.sections.filter((section) => draft[section.key]?.trim()).map((section) => `## ${section.label}\n\n${draft[section.key].trim()}`)
  const content = [`# ${draft.title.trim()}`, '', ...metadata, draft.category ? `- **分类：** ${draft.category}` : '', '', plainText(draft.bodyHtml), '', ...legacy].join('\n')
  const url = URL.createObjectURL(new Blob(['\ufeff', content], { type: 'text/markdown;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `${draft.title.trim().replace(/[\\/:*?"<>|]/g, '_')}.md`
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
</script>

<template>
  <main class="prep-page library-page" :class="`library-${mode}`">
    <div class="prep-breadcrumb"><button type="button" @click="emit('back')">工作台首页</button><span>/</span><span>教学筹备</span><span>/</span><strong>{{ config.title }}</strong></div>
    <section class="prep-hero library-hero">
      <div class="prep-hero-copy">
        <span class="prep-kicker">{{ config.kicker }} · 文献库</span>
        <h1>{{ config.title }}</h1>
        <p>{{ config.description }}</p>
        <span class="library-hero-count">{{ records.length }} 篇我的记录</span>
      </div>
      <div class="prep-hero-mark" aria-hidden="true"><el-icon><component :is="icon" /></el-icon></div>
    </section>
    <div v-if="hasWorking && !drawerOpen" class="library-recovery"><span>检测到上次未保存的{{ config.itemName }}草稿</span><el-button text type="primary" @click="resumeDraft">继续编辑 <el-icon><ArrowRight /></el-icon></el-button></div>
    <div class="library-toolbar surface-card"><div class="library-toolbar-fields"><el-input v-model="query" :prefix-icon="Search" clearable :placeholder="`搜索${config.itemName}、课题或正文`" aria-label="搜索资料"/><el-select v-model="categoryFilter" clearable placeholder="全部分类" aria-label="分类筛选"><el-option v-for="category in ['未分类', ...categories]" :key="category" :label="category" :value="category"/></el-select></div><el-button type="primary" :icon="Plus" @click="startNew()">新建{{ config.itemName }}</el-button></div>
    <div class="library-section-top"><div><span class="prep-overline">{{ mode === 'cases' ? 'CLASSROOM LIBRARY' : mode === 'papers' ? 'RESEARCH ARCHIVE' : 'TEACHING JOURNAL' }}</span><h2>{{ mode === 'cases' ? '案例卡片' : mode === 'papers' ? '论文目录' : '反思日志' }}</h2></div><span>显示 {{ filteredItems.length }} 条 · 包含 {{ config.examples.length }} 条演示素材</span></div>

    <div v-if="!filteredItems.length" class="library-empty surface-card"><el-icon><component :is="icon" /></el-icon><strong>{{ query || categoryFilter ? '没有匹配的记录' : '还没有自己的记录' }}</strong><p>试试其他关键词，或新建一篇{{ config.itemName }}。</p><el-button type="primary" plain @click="startNew()">新建内容</el-button></div>
    <div v-else-if="mode === 'cases'" class="library-card-grid"><article v-for="(item, index) in filteredItems" :key="item.id" class="library-case-card surface-card"><div class="case-card-top"><span class="case-card-number">{{ String(index + 1).padStart(2, '0') }}</span><el-tag size="small" :type="item.example ? 'info' : 'success'" effect="plain">{{ item.example ? '示例' : (item.data.category || '未分类') }}</el-tag></div><h3>{{ item.data.title }}</h3><p>{{ excerpt(item) }}</p><div class="case-card-meta"><span>{{ item.data.grade || item.data.topic || '科学课堂' }}</span><span>{{ item.updatedAt || item.tag }}</span></div><div class="case-card-actions"><el-button text type="primary" @click="openItem(item)">阅读案例 <el-icon><ArrowRight /></el-icon></el-button><el-button v-if="!item.example" text :icon="Delete" :aria-label="`删除${item.data.title}`" @click="deleteRecord(item)"/></div></article></div>
    <section v-else-if="mode === 'papers'" class="library-table-card surface-card"><el-table :data="filteredItems" stripe style="width:100%" row-key="id" @row-click="openItem"><el-table-column label="论文题目" min-width="260"><template #default="{ row }"><div class="paper-title"><el-icon><Reading /></el-icon><div><strong>{{ row.data.title }}</strong><small>{{ row.data.keywords || '未填写关键词' }}</small></div></div></template></el-table-column><el-table-column label="分类" width="120"><template #default="{ row }"><el-tag size="small" :type="row.example ? 'info' : 'success'" effect="plain">{{ row.example ? '示例' : (row.data.category || '未分类') }}</el-tag></template></el-table-column><el-table-column label="作者" width="130"><template #default="{ row }">{{ row.data.author || '未署名' }}</template></el-table-column><el-table-column label="更新时间" width="180"><template #default="{ row }">{{ row.updatedAt || '演示素材' }}</template></el-table-column><el-table-column label="操作" width="145" fixed="right"><template #default="{ row }"><el-button link type="primary" @click.stop="openItem(row)">阅读</el-button><el-button v-if="!row.example" link type="danger" @click.stop="deleteRecord(row)">删除</el-button></template></el-table-column></el-table></section>
    <div v-else class="library-timeline"><article v-for="item in filteredItems" :key="item.id" class="library-journal-row"><div class="journal-date"><strong>{{ item.data.date ? item.data.date.slice(5) : '示例' }}</strong><span>{{ item.data.date ? item.data.date.slice(0, 4) : 'JOURNAL' }}</span></div><div class="journal-marker"/><div class="journal-card surface-card"><div class="journal-card-head"><el-tag size="small" :type="item.example ? 'info' : 'success'" effect="plain">{{ item.example ? '示例' : (item.data.category || '未分类') }}</el-tag><span>{{ item.data.className || '教学记录' }}</span></div><h3>{{ item.data.title }}</h3><p>{{ excerpt(item) }}</p><div class="journal-card-bottom"><span>{{ item.data.topic || item.updatedAt || item.tag }}</span><div><el-button text type="primary" @click="openItem(item)">阅读反思 <el-icon><ArrowRight /></el-icon></el-button><el-button v-if="!item.example" text :icon="Delete" :aria-label="`删除${item.data.title}`" @click="deleteRecord(item)"/></div></div></div></article></div>

    <el-drawer v-model="drawerOpen" class="library-drawer" :size="'680px'" :before-close="requestClose" :with-header="false" destroy-on-close>
      <div class="library-drawer-shell"><header class="library-drawer-head"><div><span class="prep-overline">{{ currentLabel }}</span><h2>{{ editing ? (selectedId ? `编辑${config.itemName}` : `新建${config.itemName}`) : draft.title }}</h2></div><button type="button" aria-label="关闭详情" @click="requestClose()">×</button></header>
        <div v-if="!editing" class="library-reading"><div class="library-reading-meta"><el-tag size="small" effect="plain">{{ isExample ? '示例' : (draft.category || '未分类') }}</el-tag><span v-for="field in config.fields.filter((item) => item.key !== 'title' && draft[item.key]?.trim())" :key="field.key">{{ field.label }}：{{ draft[field.key] }}</span></div><div v-if="draft.bodyHtml && plainText(draft.bodyHtml)" class="library-rich-read" v-html="safeHtml(draft.bodyHtml)"/><div v-for="section in config.sections.filter((item) => draft[item.key]?.trim())" :key="section.key" class="library-reading-section"><h3>{{ section.label }}</h3><p>{{ draft[section.key] }}</p></div><div class="library-drawer-actions"><el-button type="primary" :icon="isExample ? Plus : EditPen" @click="beginEdit">{{ isExample ? '以此为模板新建' : '编辑记录' }}</el-button><el-button :icon="Download" @click="exportMarkdown">导出 Markdown</el-button></div></div>
        <div v-else class="library-editing"><div class="library-form-grid"><div v-for="field in config.fields" :key="field.key" class="prep-field" :class="{ wide: field.wide }"><label :for="`library-${mode}-${field.key}`">{{ field.label }}<i v-if="field.required">*</i></label><el-select v-if="field.type === 'grade'" :id="`library-${mode}-${field.key}`" v-model="draft[field.key]" clearable :placeholder="field.placeholder"><el-option v-for="grade in gradeOptions" :key="grade" :label="grade" :value="grade"/></el-select><el-date-picker v-else-if="field.type === 'date'" :id="`library-${mode}-${field.key}`" v-model="draft[field.key]" type="date" value-format="YYYY-MM-DD"/><el-input v-else :id="`library-${mode}-${field.key}`" v-model="draft[field.key]" :placeholder="field.placeholder" maxlength="160"/></div><div class="prep-field"><label :for="`library-${mode}-category`">分类</label><el-select :id="`library-${mode}-category`" v-model="draft.category" clearable placeholder="选择分类"><el-option v-for="category in categories" :key="category" :label="category" :value="category"/></el-select></div></div><div class="library-editor-label"><strong>正文内容</strong><span>可设置标题、加粗、列表等格式</span></div><div class="library-rich-editor"><Toolbar :editor="editorRef" :default-config="toolbarConfig" mode="default"/><Editor v-model="draft.bodyHtml" :default-config="editorConfig" mode="default" @onCreated="onEditorCreated"/></div><el-collapse v-if="config.sections.some((section) => draft[section.key]?.trim())" class="library-legacy"><el-collapse-item title="原有分段内容（保留并可继续编辑）" name="legacy"><div v-for="section in config.sections" :key="section.key" class="prep-field"><label :for="`legacy-${section.key}`">{{ section.label }}</label><el-input :id="`legacy-${section.key}`" v-model="draft[section.key]" type="textarea" :rows="3" :placeholder="section.hint"/></div></el-collapse-item></el-collapse><div class="library-drawer-actions"><el-button type="primary" :icon="EditPen" @click="saveRecord">保存{{ config.itemName }}</el-button><el-button @click="requestClose()">取消</el-button><span>{{ isDirty ? '修改尚未保存' : selectedId ? '当前内容已保存' : '尚未填写内容' }}</span></div></div>
      </div>
    </el-drawer>
  </main>
</template>
