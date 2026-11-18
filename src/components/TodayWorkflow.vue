<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Calendar, Connection, MagicStick } from '@element-plus/icons-vue'
import { scheduleApi } from '../data/scheduleApi'
import { apiMessage, todoApi } from '../data/todoApi'

const props = defineProps({
  courses: { type: Array, required: true }, date: String, accountId: Number,
  status: String, synced: Boolean, getToken: { type: Function, required: true },
})
const emit = defineEmits(['open-slot', 'open-feature', 'retry', 'imported'])
const selected = ref('')
const current = computed(() => props.courses.find(course => course.key === selected.value))
const lesson = computed(() => current.value?.lesson)
watch([() => props.courses, () => props.status], ([courses, status]) => {
  if (status !== 'ready') return
  if (!courses.some(course => course.key === selected.value)) selected.value = (courses.find(course => course.lesson) || courses[0])?.key || ''
}, { immediate: true })
const open = ref(false)
const reading = ref(false)
const saving = ref(false)
const equipment = ref([])
const error = ref('')
const picked = computed(() => equipment.value.filter(item => item.checked))
let controller

function clearReview() {
  controller?.abort()
  controller = null
  open.value = false
  reading.value = false
  equipment.value = []
  error.value = ''
}
watch([() => props.date, () => props.accountId, () => props.status, selected, () => lesson.value?.id, () => lesson.value?.materials], clearReview)
onBeforeUnmount(clearReview)

async function readEquipment() {
  if (!lesson.value?.materials?.trim() || reading.value || saving.value) return
  clearReview()
  const request = new AbortController()
  controller = request
  open.value = true
  reading.value = true
  try {
    const items = await scheduleApi.equipment(props.getToken(), lesson.value.id, request.signal)
    if (!request.signal.aborted) equipment.value = items.map(item => ({ ...item, checked: true }))
  } catch (reason) {
    if (!request.signal.aborted) error.value = apiMessage(reason)
  } finally {
    if (controller === request) reading.value = false
  }
}

async function saveEquipment() {
  if (saving.value || !picked.value.length || !lesson.value) return
  saving.value = true
  error.value = ''
  const request = controller
  const token = props.getToken()
  const lessonId = lesson.value.id
  const date = props.date
  try {
    const items = await Promise.all(picked.value.map(async item => {
      const identity = JSON.stringify([date, lessonId, item.name, item.quantity])
      const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(identity))
      const key = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('')
      const description = /每组|每小组|每班|每人|每桌/.test(item.evidence) ? `准备${item.name} · 原文：${item.evidence}` : `准备${item.name}${item.quantity ? '（' + item.quantity + '）' : '（数量待核对）'}`
      const content = [...description].length > 80 ? [...description].slice(0, 79).join('') + '…' : description
      return { content, date, legacy_key: 'equipment:' + key }
    }))
    if (request?.signal.aborted || token !== props.getToken()) return
    const result = await todoApi.import(token, items)
    if (token !== props.getToken()) return
    emit('imported')
    if (request?.signal.aborted) return
    ElMessage.success(result.imported ? `已添加 ${result.imported} 项器材待办` : '所选器材都已加入过当天待办')
    clearReview()
  } catch (reason) {
    if (!request?.signal.aborted) error.value = apiMessage(reason)
  } finally { saving.value = false }
}
</script>

<template>
  <section class="surface-card workflow" aria-labelledby="workflow-title">
    <div class="workflow-heading"><h2 id="workflow-title">今日 AI 课前协同</h2><span>{{ synced ? '账号课表' : '浏览器课表' }}</span></div>
    <div class="workflow-grid">
      <article>
        <h3><el-icon><Calendar /></el-icon>今日备课包</h3>
        <p v-if="status === 'loading'" role="status">正在核对课程与备课包…</p>
        <template v-else-if="status === 'error'"><p>暂时无法读取账号数据。</p><el-button size="small" @click="emit('retry')">重新读取</el-button></template>
        <template v-else-if="current">
          <el-select v-model="selected" aria-label="选择今天的科学课" size="small"><el-option v-for="course in courses" :key="course.key" :value="course.key" :label="course.time + ' · ' + course.label" /></el-select>
          <p><strong>{{ lesson?.title || '这节课还没有关联备课包' }}</strong><br v-if="lesson" />{{ lesson ? (lesson.revision ? `课件 v${lesson.revision} · ${lesson.slideCount} 页` : '已备课，尚未生成课件') : '' }}</p>
          <el-button size="small" @click="emit('open-slot', current)">{{ lesson ? '进入备课包' : '关联备课包' }}</el-button>
        </template>
        <template v-else><p>今天没有安排常规科学课。</p><el-button size="small" @click="emit('open-feature', 'prep', 'AI 备课中心')">准备其他课程</el-button></template>
      </article>
      <article>
        <h3><el-icon><MagicStick /></el-icon>实验器材待办</h3>
        <p>{{ status !== 'ready' ? '读取课程后可核对器材。' : lesson?.materials?.trim() ? `从《${lesson.title}》的参考资料中提取器材和数量。` : lesson ? '在备课包中补充实验器材或教材摘录后即可提取。' : '选择有关联备课包的课程后，可按原文提取器材。' }}</p>
        <el-button type="primary" plain size="small" :disabled="status !== 'ready' || !lesson?.materials?.trim()" @click="readEquipment">AI 提取器材清单</el-button>
      </article>
      <article>
        <h3><el-icon><Connection /></el-icon>科学创作与识图</h3>
        <p>选择本课所需的任务，在 AI 对话中补充题目或照片。</p>
        <div class="skill-actions"><el-button size="small" @click="emit('open-feature', 'images', '科学示意图生成')">画科学示意图</el-button><el-button size="small" @click="emit('open-feature', 'recognition', '器材识别')">拍照识器材</el-button></div>
      </article>
    </div>
    <el-dialog v-model="open" title="核对实验器材" width="min(92vw, 560px)" :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving" @close="clearReview">
      <p>{{ lesson?.title }} · {{ date }}</p>
      <p v-if="reading" role="status">AI 正在逐项核对参考资料…</p>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <p v-if="!reading && !error && !equipment.length">资料中没有明确列出的器材。可补充器材后再提取。</p>
      <div v-for="item in equipment" :key="JSON.stringify([item.name, item.quantity])" class="equipment-item">
        <el-checkbox v-model="item.checked" :disabled="saving">{{ item.name }} · {{ item.quantity || '数量待核对' }}</el-checkbox>
        <small>原文「{{ item.evidence }}」</small>
      </div>
      <template #footer><el-button :disabled="saving" @click="clearReview">关闭</el-button><el-button v-if="error && !equipment.length" @click="readEquipment">重试</el-button><el-button type="primary" :loading="saving" :disabled="!picked.length || reading" @click="saveEquipment">将 {{ picked.length }} 项加入今日待办</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>
.workflow { padding: clamp(16px, 2vw, 24px); }
.workflow-heading, .workflow h3 { display: flex; align-items: center; gap: 10px; }
.workflow-heading { justify-content: space-between; margin-bottom: 16px; }
.workflow h2, .workflow h3 { margin: 0; color: var(--el-text-color-primary); }
.workflow h2 { font-size: 18px; }
.workflow h3 { margin-bottom: 12px; font-size: 15px; }
.workflow-heading span, .equipment-item small { color: var(--el-text-color-secondary); font-size: 12px; }
.workflow-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.workflow-grid article { border: 1px solid var(--el-border-color-light); border-radius: 8px; padding: 16px; }
.workflow-grid article:nth-child(1) i { color: #378375; }
.workflow-grid article:nth-child(2) i { color: #986329; }
.workflow-grid article:nth-child(3) i { color: #6856a4; }
.workflow-grid p { font-size: 13px; line-height: 1.6; color: var(--el-text-color-regular); overflow-wrap: anywhere; }
.skill-actions { display: flex; flex-wrap: wrap; gap: 6px; }
.skill-actions .el-button { margin: 0; }
.equipment-item { display: grid; padding: 6px 0; border-bottom: 1px solid var(--el-border-color-light); }
.equipment-item small { overflow-wrap: anywhere; }
@media (max-width: 850px) { .workflow-grid { grid-template-columns: 1fr; } }
</style>
