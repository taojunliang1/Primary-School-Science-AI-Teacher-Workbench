<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowRight, Compass, Delete, Document, Download, EditPen,
  Notebook, Plus, Reading, Search,
} from '@element-plus/icons-vue'
import { gradeOptions, preparationModes } from '../data/teachingPrep'

const props = defineProps({ mode: { type: String, required: true } })
const emit = defineEmits(['back'])
const config = preparationModes[props.mode]
const icons = { inquiry: Compass, cases: Document, papers: Reading, reflections: Notebook }
const storageKey = `science-workbench-prep-${props.mode}-v1`
const workingKey = `${storageKey}-working`
const todayKey = () => {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}
function blankDraft() {
  const result = Object.fromEntries([...config.fields, ...config.sections].map((field) => [field.key, '']))
  if (props.mode === 'inquiry') result.duration = '40 分钟'
  if (props.mode === 'reflections') result.date = todayKey()
  return result
}
function normalizedDraft(source) {
  const result = blankDraft()
  for (const key of Object.keys(result)) {
    if (typeof source?.[key] === 'string') result[key] = source[key]
  }
  return result
}
function readRecords() {
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || '[]')
    return Array.isArray(saved) ? saved.filter((item) => item && typeof item.id === 'string' && item.data && typeof item.data.title === 'string') : []
  } catch { return [] }
}

const records = ref(readRecords())
let working = null
try { working = JSON.parse(localStorage.getItem(workingKey) || 'null') } catch { /* 使用空白草稿 */ }
const draft = reactive(working?.data ? normalizedDraft(working.data) : blankDraft())
const selectedId = ref(records.value.some((record) => record.id === working?.selectedId) ? working.selectedId : null)
const baseline = ref(typeof working?.baseline === 'string' ? working.baseline : JSON.stringify(blankDraft()))
const query = ref('')
const activeStep = ref(0)
const lastSaved = ref(records.value.find((record) => record.id === selectedId.value)?.updatedAt || '')
const filledSections = computed(() => config.sections.filter((section) => draft[section.key]?.trim()).length)
const wordCount = computed(() => [draft.title, ...config.sections.map((section) => draft[section.key])].join('').replace(/\s/g, '').length)
const isDirty = computed(() => JSON.stringify(draft) !== baseline.value)
const filteredRecords = computed(() => {
  const needle = query.value.trim().toLowerCase()
  return records.value.filter((record) => !needle || `${record.data.title} ${record.data.topic || ''} ${record.data.keywords || ''}`.toLowerCase().includes(needle))
})
watch([draft, selectedId, baseline], () => {
  try {
    localStorage.setItem(workingKey, JSON.stringify({ data: normalizedDraft(draft), selectedId: selectedId.value, baseline: baseline.value }))
  } catch { /* 浏览器空间不足时，仍可通过“保存”查看提示。 */ }
}, { deep: true })

async function discardIfNeeded() {
  if (!isDirty.value) return true
  try {
    await ElMessageBox.confirm('当前内容尚未保存，继续将放弃这些修改。', '切换内容', {
      confirmButtonText: '继续', cancelButtonText: '取消', type: 'warning',
    })
    return true
  } catch { return false }
}

async function startNew() {
  if (!await discardIfNeeded()) return
  Object.assign(draft, blankDraft())
  selectedId.value = null
  baseline.value = JSON.stringify(draft)
  lastSaved.value = ''
  activeStep.value = 0
}

async function openRecord(record) {
  if (selectedId.value === record.id) return
  if (!await discardIfNeeded()) return
  Object.assign(draft, normalizedDraft(record.data))
  selectedId.value = record.id
  baseline.value = JSON.stringify(draft)
  lastSaved.value = record.updatedAt || ''
  activeStep.value = 0
}

async function useExample(example) {
  if (!await discardIfNeeded()) return
  Object.assign(draft, normalizedDraft(example.data))
  selectedId.value = null
  baseline.value = JSON.stringify(draft)
  lastSaved.value = ''
  activeStep.value = 0
  ElMessage.info('已载入演示素材，修改后可保存为自己的记录')
}

function saveRecord() {
  if (!draft.title.trim()) return ElMessage.warning(`请先填写${config.fields[0].label}`)
  if (!filledSections.value) return ElMessage.warning('请至少填写一个正文部分')
  const savedAt = new Date().toLocaleString('zh-CN', { hour12: false })
  const id = selectedId.value || `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  const record = { id, updatedAt: savedAt, data: normalizedDraft(draft) }
  const next = [record, ...records.value.filter((item) => item.id !== id)]
  try {
    localStorage.setItem(storageKey, JSON.stringify(next))
  } catch { return ElMessage.error('保存失败，请检查浏览器本地存储空间') }
  records.value = next
  selectedId.value = id
  baseline.value = JSON.stringify(draft)
  lastSaved.value = savedAt
  ElMessage.success(`${config.itemName}已保存到当前浏览器`)
}

async function deleteRecord(record) {
  try {
    await ElMessageBox.confirm(`确定删除“${record.data.title}”吗？此操作无法从页面恢复。`, '删除记录', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
    })
  } catch { return }
  const next = records.value.filter((item) => item.id !== record.id)
  try {
    localStorage.setItem(storageKey, JSON.stringify(next))
  } catch { return ElMessage.error('删除失败，请检查浏览器本地存储空间') }
  records.value = next
  if (selectedId.value === record.id) {
    Object.assign(draft, blankDraft())
    selectedId.value = null
    baseline.value = JSON.stringify(draft)
    lastSaved.value = ''
  }
  ElMessage.success('记录已删除')
}

function exportMarkdown() {
  if (!draft.title.trim()) return ElMessage.warning('请先填写标题再导出')
  const metadata = config.fields.filter((field) => field.key !== 'title' && draft[field.key]?.trim())
    .map((field) => `- **${field.label}：** ${draft[field.key].trim()}`)
  const sections = config.sections.map((section) => `## ${section.label}\n\n${draft[section.key]?.trim() || '（待填写）'}`)
  const content = [`# ${draft.title.trim()}`, '', ...metadata, '', ...sections, '', '> 本文档由小学科学教师工作台前端整理；未调用 AI。'].join('\n')
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
  <main class="prep-page" :class="`prep-${mode}`">
    <div class="prep-breadcrumb"><button type="button" @click="emit('back')">工作台首页</button><span>/</span><span>教学筹备</span><span>/</span><strong>{{ config.title }}</strong></div>

    <section class="prep-hero"><div class="prep-hero-copy"><span class="prep-kicker">{{ config.kicker }} · 前端体验版</span><h1>{{ config.title }}</h1><p>{{ config.description }}</p></div><div class="prep-hero-mark" aria-hidden="true"><el-icon><component :is="icons[mode]" /></el-icon></div></section>

    <div class="prep-notice"><span class="prep-notice-dot"/><span>{{ config.hint }} 本阶段不调用 AI 或后端；未保存的输入会暂存在当前浏览器，正式记录请点击“保存”。</span></div>

    <div class="prep-shelf">
      <section class="prep-shelf-card surface-card" :aria-label="config.collection"><div class="prep-shelf-heading"><div><span class="prep-overline">MY WORK</span><h2>{{ config.collection }} <small>{{ records.length }}</small></h2></div><el-button type="primary" :icon="Plus" size="small" @click="startNew">新建</el-button></div><el-input v-model="query" :prefix-icon="Search" clearable :placeholder="`搜索${config.itemName}标题`" aria-label="搜索已保存的记录"/><div v-if="filteredRecords.length" class="prep-record-list"><div v-for="record in filteredRecords" :key="record.id" class="prep-record" :class="{ active: selectedId === record.id }"><button type="button" @click="openRecord(record)"><strong>{{ record.data.title }}</strong><span>{{ record.updatedAt }}</span></button><el-button text :icon="Delete" :aria-label="`删除${record.data.title}`" @click="deleteRecord(record)"/></div></div><div v-else class="prep-shelf-empty">{{ records.length ? '没有找到匹配的记录' : '还没有保存记录。可从空白页开始，也可载入右侧示例。' }}</div></section>
      <section class="prep-shelf-card surface-card" aria-label="演示素材"><div class="prep-shelf-heading"><div><span class="prep-overline">STARTER IDEAS</span><h2>{{ mode === 'cases' ? '示例案例' : '写作示例' }}</h2></div><span class="prep-example-badge">仅供参考</span></div><div class="prep-examples"><button v-for="example in config.examples" :key="example.title" type="button" @click="useExample(example)"><span>{{ example.tag }}</span><strong>{{ example.title }}</strong><el-icon><ArrowRight /></el-icon></button></div></section>
    </div>

    <section class="inquiry-process surface-card" aria-label="六步探究流程"><div class="inquiry-process-head"><div><span class="prep-overline">INQUIRY PATH</span><h2>六步探究流程</h2></div><span>已填写 {{ filledSections }} / 6 步</span></div><div class="inquiry-step-track"><button v-for="(section, index) in config.sections" :key="section.key" type="button" :class="{ active: activeStep === index, complete: draft[section.key]?.trim() }" @click="activeStep = index"><span>{{ draft[section.key]?.trim() && activeStep !== index ? '✓' : String(index + 1).padStart(2, '0') }}</span><strong>{{ section.label }}</strong></button></div></section>

    <div class="prep-layout inquiry-layout">
      <section class="prep-editor-card surface-card" :aria-label="`编辑${config.itemName}`"><div class="prep-card-heading"><span class="prep-step">01</span><div><h2>编辑{{ config.itemName }}</h2><p>{{ selectedId ? `正在编辑已保存记录 · ${lastSaved}` : '创建新内容，填写后点击保存' }}</p></div></div>
        <div class="prep-form-grid"><div v-for="field in config.fields" :key="field.key" class="prep-field" :class="{ wide: field.wide }"><label :for="`${mode}-${field.key}`">{{ field.label }}<i v-if="field.required">*</i></label><el-select v-if="field.type === 'grade'" :id="`${mode}-${field.key}`" v-model="draft[field.key]" :placeholder="field.placeholder" clearable style="width:100%"><el-option v-for="grade in gradeOptions" :key="grade" :label="grade" :value="grade"/></el-select><el-select v-else-if="field.type === 'duration'" :id="`${mode}-${field.key}`" v-model="draft[field.key]" style="width:100%"><el-option v-for="duration in ['35 分钟', '40 分钟', '45 分钟', '80 分钟']" :key="duration" :label="duration" :value="duration"/></el-select><el-date-picker v-else-if="field.type === 'date'" :id="`${mode}-${field.key}`" v-model="draft[field.key]" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width:100%"/><el-input v-else :id="`${mode}-${field.key}`" v-model="draft[field.key]" :placeholder="field.placeholder" maxlength="160" clearable/></div></div>
        <div class="prep-section-heading"><h3>当前步骤 · {{ config.sections[activeStep].label }}</h3><span>{{ activeStep + 1 }} / 6</span></div>
        <div class="inquiry-active-step"><div class="inquiry-active-number">{{ String(activeStep + 1).padStart(2, '0') }}</div><h3>{{ config.sections[activeStep].label }}</h3><p>{{ config.sections[activeStep].hint }}</p><el-input :id="`${mode}-${config.sections[activeStep].key}`" v-model="draft[config.sections[activeStep].key]" type="textarea" :rows="7" maxlength="1500" :placeholder="config.sections[activeStep].hint"/><div class="inquiry-step-actions"><el-button :disabled="activeStep === 0" @click="activeStep--">上一步</el-button><el-button :disabled="activeStep === 5" type="primary" plain @click="activeStep++">下一步</el-button></div></div>
        <div class="prep-editor-actions"><el-button type="primary" :icon="EditPen" @click="saveRecord">{{ selectedId ? '保存修改' : `保存${config.itemName}` }}</el-button><span>{{ isDirty ? '修改已临时保留，尚未保存为记录' : selectedId ? '已保存' : '尚未保存为记录' }}</span></div>
      </section>

      <section class="prep-preview-card surface-card" :aria-label="config.preview"><div class="prep-card-heading"><span class="prep-step">02</span><div><h2>{{ config.preview }}</h2><p>随左侧输入实时更新</p></div></div><div class="prep-preview-paper"><div class="prep-preview-top"><span>{{ config.kicker }}</span><span>{{ wordCount }} 字</span></div><h3>{{ draft.title.trim() || '在左侧填写标题' }}</h3><div class="prep-preview-meta"><span v-for="field in config.fields.filter((item) => item.key !== 'title' && draft[item.key]?.trim())" :key="field.key">{{ field.label }}：{{ draft[field.key] }}</span></div><div v-if="!filledSections" class="prep-preview-empty"><el-icon><component :is="icons[mode]" /></el-icon><strong>内容预览将在这里出现</strong><p>填写任一部分，右侧会同步排版展示。</p></div><div v-for="(section, index) in config.sections.filter((item) => draft[item.key]?.trim())" :key="section.key" class="prep-preview-section"><h4><span>{{ String(index + 1).padStart(2, '0') }}</span>{{ section.label }}</h4><p>{{ draft[section.key] }}</p></div><div class="prep-preview-footer">小学科学教师工作台 · 本地演示文稿</div></div><el-button class="inquiry-report-button" type="primary" size="large" :icon="Download" @click="exportMarkdown">导出完整探究报告</el-button></section>
    </div>
  </main>
</template>
