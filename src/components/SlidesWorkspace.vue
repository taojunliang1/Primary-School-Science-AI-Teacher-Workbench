<script setup>
import { computed, nextTick, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft, ArrowRight, Check, CirclePlus, Delete, Document,
  Download, EditPen, MagicStick, RefreshRight,
} from '@element-plus/icons-vue'

defineEmits(['back'])

const storageKey = 'science-workbench-slides-draft-v1'
const emptyForm = () => ({
  topic: '', grade: '', duration: 40, template: 'inquiry',
  objectives: '', focus: '', materials: '',
})
const form = reactive(emptyForm())
const formRef = ref(null)
const outline = ref([])
const selectedIndex = ref(0)
const savedAt = ref('')
const previewSource = ref('')

const templates = [
  { key: 'inquiry', name: '探究式课堂', detail: '从问题到证据，呈现完整探究链', steps: '8 页结构' },
  { key: 'experiment', name: '实验演示', detail: '突出器材、安全、操作与记录', steps: '7 页结构' },
  { key: 'knowledge', name: '知识讲解', detail: '用现象、概念和讨论组织课堂', steps: '6 页结构' },
]
const grades = ['一年级', '二年级', '三年级', '四年级', '五年级', '六年级']
const rules = {
  topic: [{ required: true, whitespace: true, message: '请填写课程主题', trigger: 'blur' }],
  grade: [{ required: true, message: '请选择年级', trigger: 'change' }],
  objectives: [{ required: true, whitespace: true, message: '请填写教学目标', trigger: 'blur' }],
}

try {
  const saved = JSON.parse(localStorage.getItem(storageKey) || 'null')
  if (saved && typeof saved === 'object') {
    for (const key of Object.keys(emptyForm())) {
      if (saved.form?.[key] !== undefined) form[key] = saved.form[key]
    }
    if (Array.isArray(saved.outline)) {
      outline.value = saved.outline.filter((page) => page && typeof page.title === 'string' && typeof page.content === 'string')
    }
    savedAt.value = typeof saved.savedAt === 'string' ? saved.savedAt : ''
    previewSource.value = typeof saved.previewSource === 'string' ? saved.previewSource : ''
  }
} catch {
  // 旧草稿损坏时使用空白表单。
}

const currentPage = computed(() => outline.value[selectedIndex.value] || null)
const hasFormChanges = computed(() => Boolean(outline.value.length && previewSource.value && previewSource.value !== JSON.stringify(form)))

function page(title, content) {
  return { id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, title, content }
}

function buildOutline() {
  const topic = form.topic.trim()
  const objectives = form.objectives.trim()
  const focus = form.focus.trim() || '请结合教材与学生已有经验补充本课重点。'
  const materials = form.materials.trim() || '请补充本课所需器材、图片或观察材料。'
  const cover = page(topic, `${form.grade}科学 · ${form.duration} 分钟\n教学目标：${objectives}`)

  if (form.template === 'experiment') {
    return [
      cover,
      page('实验任务与安全提示', `围绕“${topic}”明确本节课要完成的实验任务。\n安全提醒：根据实际器材和学生年龄补充操作规范。`),
      page('提出问题与作出假设', `我们要通过实验回答什么问题？\n请学生记录自己的预测，并说明理由。`),
      page('器材准备', materials),
      page('实验步骤', `1. 检查器材，明确分组与分工。\n2. 按照教师确认的步骤开展操作。\n3. 及时记录现象和数据。`),
      page('记录与分析', `用表格、图示或照片整理实验结果。\n比较不同小组的证据，关注异常数据。\n教学重点：${focus}`),
      page('交流与反思', `根据证据回答最初的问题。\n回顾实验方法，并提出可以继续研究的新问题。`),
    ]
  }

  if (form.template === 'knowledge') {
    return [
      cover,
      page('身边的科学现象', `展示与“${topic}”相关的生活现象，引导学生说出观察和疑问。`),
      page('本课学习目标', objectives),
      page('核心概念与图解', `围绕“${topic}”整理关键概念。\n教学重点：${focus}\n可在此页添加实物照片、结构图或示意图。`),
      page('观察与讨论', `请学生比较、分类或解释一组现象。\n准备材料：${materials}`),
      page('课堂小结与应用', `用自己的话总结今天学到的科学知识。\n举一个生活中的应用，并提出一个新问题。`),
    ]
  }

  return [
    cover,
    page('提出问题', `从“${topic}”相关现象出发，让学生观察并提出可探究的问题。\n教学目标：${objectives}`),
    page('作出假设', '请学生说出自己的预测，并解释预测的依据。\n可以记录不同小组的观点。'),
    page('制定计划', `讨论变量、观察方法、分工与安全事项。\n准备材料：${materials}`),
    page('搜集证据', '通过观察、实验、测量或查阅资料获取证据。\n在此页放入记录表或操作照片。'),
    page('处理信息', `整理并比较数据，尝试用图表说明发现。\n教学重点：${focus}`),
    page('得出结论', '根据证据回答最初的问题，区分观察事实与推测。'),
    page('交流与延伸', '分享探究过程与结论，反思方法，并提出新的研究问题。'),
  ]
}

async function createPreview() {
  try {
    await formRef.value.validate()
  } catch {
    ElMessage.warning('请先补全课程主题、年级和教学目标')
    return
  }
  if (outline.value.length) {
    try {
      await ElMessageBox.confirm('重新预览会覆盖当前已编辑的课件页，是否继续？', '重新预览', {
        confirmButtonText: '继续', cancelButtonText: '取消', type: 'warning',
      })
    } catch { return }
  }
  outline.value = buildOutline()
  selectedIndex.value = 0
  previewSource.value = JSON.stringify(form)
  ElMessage.success('示例结构已就绪，可在右侧逐页编辑')
}

function saveDraft() {
  try {
    const time = new Date().toLocaleString('zh-CN', { hour12: false })
    localStorage.setItem(storageKey, JSON.stringify({ form: { ...form }, outline: outline.value, savedAt: time, previewSource: previewSource.value }))
    savedAt.value = time
    ElMessage.success('草稿已保存到当前浏览器')
  } catch {
    ElMessage.error('保存失败，请检查浏览器本地存储空间')
  }
}

async function clearDraft() {
  try {
    await ElMessageBox.confirm('将清空表单、预览和此浏览器中的草稿，确定继续？', '清空草稿', {
      confirmButtonText: '清空', cancelButtonText: '取消', type: 'warning',
    })
  } catch { return }
  Object.assign(form, emptyForm())
  outline.value = []
  selectedIndex.value = 0
  previewSource.value = ''
  savedAt.value = ''
  localStorage.removeItem(storageKey)
  await nextTick()
  formRef.value?.clearValidate()
  ElMessage.success('已清空草稿')
}

function addPage() {
  outline.value.splice(selectedIndex.value + 1, 0, page('新课件页', '在这里填写本页内容、提问或课堂活动。'))
  selectedIndex.value += 1
}

function deletePage() {
  if (outline.value.length <= 1) return ElMessage.warning('至少保留一页课件')
  outline.value.splice(selectedIndex.value, 1)
  selectedIndex.value = Math.min(selectedIndex.value, outline.value.length - 1)
}

function movePage(offset) {
  const target = selectedIndex.value + offset
  if (target < 0 || target >= outline.value.length) return
  const [item] = outline.value.splice(selectedIndex.value, 1)
  outline.value.splice(target, 0, item)
  selectedIndex.value = target
}

function exportOutline() {
  if (!outline.value.length) return ElMessage.warning('请先预览课件结构')
  const title = form.topic.trim() || '科学课件'
  const content = [
    `${title} · 课件大纲`,
    `${form.grade}｜${form.duration}分钟｜${templates.find((item) => item.key === form.template)?.name || '课件'}`,
    '说明：本大纲由前端固定模板整理，未调用 AI。',
    '',
    ...outline.value.flatMap((item, index) => [`第 ${index + 1} 页｜${item.title}`, item.content, '']),
  ].join('\n')
  const url = URL.createObjectURL(new Blob(['\ufeff', content], { type: 'text/plain;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `${title.replace(/[\\/:*?"<>|]/g, '_')}-课件大纲.txt`
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
</script>

<template>
  <main class="slides-page">
    <div class="slides-breadcrumb"><button type="button" @click="$emit('back')">工作台首页</button><span>/</span><span>教学筹备</span><span>/</span><strong>科学课件生成</strong></div>

    <section class="slides-hero">
      <div class="slides-hero-copy"><span class="slides-eyebrow"><el-icon><MagicStick /></el-icon> 教学筹备 · 前端体验版</span><h1>科学课件生成</h1><p>填好备课信息，先用示例模板搭建课件结构；您可以逐页调整，整理成适合自己课堂的大纲。</p><div class="slides-hero-tags"><span>六步探究流程</span><span>逐页编辑</span><span>本地草稿</span></div></div>
      <div class="slides-hero-art" aria-hidden="true"><div class="art-circle circle-one"/><div class="art-circle circle-two"/><el-icon><Document /></el-icon><span>SCIENCE</span></div>
    </section>

    <div class="slides-notice"><span class="notice-dot"/><strong>演示模式</strong><span>这里使用固定模板预览结构，不会调用 AI，也不会上传您填写的内容。保存草稿只存放在当前浏览器。</span></div>

    <div class="slides-layout">
      <section class="slides-form-card surface-card" aria-labelledby="slides-form-title">
        <div class="slides-card-heading"><span class="slides-step">01</span><div><h2 id="slides-form-title">填写备课信息</h2><p>先确定本节课的主题与教学目标</p></div></div>
        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="slides-form">
          <el-form-item label="课程主题" prop="topic"><el-input v-model="form.topic" maxlength="60" show-word-limit placeholder="例如：探索水的浮力" clearable /></el-form-item>
          <div class="slides-form-row"><el-form-item label="适用年级" prop="grade"><el-select v-model="form.grade" placeholder="选择年级" style="width:100%"><el-option v-for="grade in grades" :key="grade" :label="grade" :value="grade" /></el-select></el-form-item><el-form-item label="课时长度"><el-select v-model="form.duration" style="width:100%"><el-option :value="35" label="35 分钟"/><el-option :value="40" label="40 分钟"/><el-option :value="45" label="45 分钟"/></el-select></el-form-item></div>
          <el-form-item label="教学目标" prop="objectives"><el-input v-model="form.objectives" type="textarea" :rows="3" maxlength="500" show-word-limit placeholder="例如：能够描述物体在水中的沉浮现象；能用观察记录支持自己的解释。" /></el-form-item>
          <el-form-item label="教学重点 / 难点"><el-input v-model="form.focus" type="textarea" :rows="2" maxlength="300" placeholder="选填：本节课特别需要学生理解或突破的内容" /></el-form-item>
          <el-form-item label="实验器材与素材"><el-input v-model="form.materials" type="textarea" :rows="2" maxlength="300" placeholder="选填：烧杯、水、不同材料的小物体、观察记录单等" /></el-form-item>
          <el-form-item label="课件结构"><div class="slides-template-grid"><button v-for="item in templates" :key="item.key" type="button" class="slides-template" :class="{ active: form.template === item.key }" :aria-pressed="form.template === item.key" @click="form.template = item.key"><span class="template-check"><el-icon v-if="form.template === item.key"><Check /></el-icon></span><strong>{{ item.name }}</strong><small>{{ item.detail }}</small><em>{{ item.steps }}</em></button></div></el-form-item>
          <div class="slides-form-actions"><el-button type="primary" :icon="MagicStick" size="large" @click="createPreview">预览示例大纲</el-button><el-button :icon="Check" size="large" @click="saveDraft">保存草稿</el-button><el-button text :icon="RefreshRight" @click="clearDraft">清空</el-button></div>
          <p class="slides-save-note">{{ savedAt ? `上次保存：${savedAt} · 仅保存在此浏览器` : '尚未保存草稿 · 切换页面前请点击“保存草稿”' }}</p>
        </el-form>
      </section>

      <section class="slides-preview-card surface-card" aria-labelledby="slides-preview-title">
        <div class="slides-card-heading"><span class="slides-step">02</span><div><h2 id="slides-preview-title">课件结构预览</h2><p>逐页查看标题与内容，直接编辑文字</p></div><el-tag v-if="outline.length" size="small" effect="plain">{{ outline.length }} 页</el-tag></div>
        <div v-if="!outline.length" class="slides-preview-empty"><div class="empty-illustration"><el-icon><Document /></el-icon><span>✦</span></div><h3>从一节科学课开始</h3><p>填写左侧的课程主题、年级和教学目标，点击“预览示例大纲”，即可在这里查看可编辑的课件结构。</p><span>示例模板 · 无 AI 调用</span></div>
        <template v-else>
          <div v-if="hasFormChanges" class="slides-changed-note">备课信息已修改。点击“预览示例大纲”可按新信息重新整理结构；当前编辑内容会被覆盖。</div>
          <div class="slides-preview-tools"><span>点击页码切换预览</span><el-button text :icon="Download" @click="exportOutline">导出 TXT 大纲</el-button></div>
          <div class="slides-page-list" role="tablist" aria-label="课件页列表"><button v-for="(item, index) in outline" :key="item.id" type="button" role="tab" :aria-selected="selectedIndex === index" class="slides-page-tab" :class="{ active: selectedIndex === index }" @click="selectedIndex = index"><span>{{ String(index + 1).padStart(2, '0') }}</span><strong>{{ item.title || '未命名页面' }}</strong></button></div>
          <div class="slides-canvas" v-if="currentPage"><div class="slides-canvas-top"><span>科学课堂 · 第 {{ selectedIndex + 1 }} 页</span><el-icon><EditPen /></el-icon></div><h3>{{ currentPage.title || '未命名页面' }}</h3><p>{{ currentPage.content || '在下方填写本页内容。' }}</p><span class="slides-canvas-footer">{{ form.grade || '小学科学' }} · {{ form.topic || '课程主题' }}</span></div>
          <div class="slides-editor" v-if="currentPage"><div class="slides-editor-title"><el-icon><EditPen /></el-icon><strong>编辑当前页</strong></div><el-input v-model="currentPage.title" maxlength="60" placeholder="页面标题" aria-label="页面标题"/><el-input v-model="currentPage.content" type="textarea" :rows="4" maxlength="1200" placeholder="页面内容" aria-label="页面内容"/></div>
          <div class="slides-page-actions"><el-button :icon="ArrowLeft" :disabled="selectedIndex === 0" @click="movePage(-1)">前移</el-button><el-button :icon="ArrowRight" :disabled="selectedIndex === outline.length - 1" @click="movePage(1)">后移</el-button><el-button :icon="CirclePlus" @click="addPage">添加页</el-button><el-button :icon="Delete" :disabled="outline.length <= 1" @click="deletePage">删除页</el-button></div>
        </template>
      </section>
    </div>
  </main>
</template>
