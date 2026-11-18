<script setup>
import { computed, ref, watch } from 'vue'
import { ArrowLeft, ArrowRight, Document, Download, View } from '@element-plus/icons-vue'
import { prepareChatArtifactDownload, previewChatArtifact } from '../data/chatApi'
import { apiMessage } from '../data/todoApi'

const props = defineProps({
  artifact: { type: Object, required: true },
  getToken: { type: Function, required: true },
})

const filename = computed(() => props.artifact.filename || 'presentation.pptx')
const metadata = computed(() => ['PowerPoint', props.artifact.slideCount ? props.artifact.slideCount + ' 页' : ''].filter(Boolean).join(' · '))
const opened = ref(false)
const page = ref(1)
const slideCount = ref(0)
const previewUrl = ref('')
const loading = ref(false)
const previewError = ref('')
const downloading = ref(false)
const downloadError = ref('')

function open() {
  page.value = 1
  opened.value = true
}

watch([opened, page], async ([visible, index], _previous, onCleanup) => {
  previewUrl.value = ''
  previewError.value = ''
  loading.value = false
  if (!visible) return
  const token = props.getToken()
  if (!token) {
    previewError.value = '请重新登录后打开文件。'
    return
  }
  const controller = new AbortController()
  let url = ''
  onCleanup(() => {
    controller.abort()
    if (url) URL.revokeObjectURL(url)
  })
  loading.value = true
  try {
    const result = await previewChatArtifact({ artifactId: props.artifact.id, token, page: index, signal: controller.signal })
    if (controller.signal.aborted) return
    url = URL.createObjectURL(result.image)
    previewUrl.value = url
    slideCount.value = result.slideCount
  } catch (error) {
    if (!controller.signal.aborted) previewError.value = error.message
  } finally {
    if (!controller.signal.aborted) loading.value = false
  }
})

async function download() {
  if (downloading.value) return
  downloadError.value = ''
  const token = props.getToken()
  if (!token) {
    downloadError.value = '请重新登录后下载文件。'
    return
  }
  downloading.value = true
  try {
    const url = await prepareChatArtifactDownload({ artifactId: props.artifact.id, token })
    const link = document.createElement('a')
    link.href = url
    link.download = filename.value
    document.body.append(link)
    link.click()
    link.remove()
  } catch (error) {
    downloadError.value = error.response?.status === 401 ? '请重新登录后下载文件。' : apiMessage(error)
  } finally {
    downloading.value = false
  }
}
</script>

<template>
  <div class="chat-artifact-entry">
    <div class="chat-artifact">
      <button class="chat-artifact-main" type="button" :aria-label="'打开 ' + filename" @click="open">
        <span class="chat-artifact-icon"><el-icon><Document /></el-icon></span>
        <span class="chat-artifact-copy">
          <strong :title="filename">{{ filename }}</strong>
          <small>{{ metadata }}</small>
        </span>
      </button>
      <div class="chat-artifact-actions">
        <el-button :icon="View" size="small" @click="open">打开</el-button>
        <el-button :icon="Download" size="small" :loading="downloading" @click="download">下载</el-button>
      </div>
    </div>
    <p v-if="downloadError && !opened" class="chat-file-error" role="alert">{{ downloadError }}</p>

    <el-dialog v-model="opened" :title="filename" width="min(900px, calc(100vw - 28px))" append-to-body destroy-on-close>
      <div class="chat-file-preview" :aria-busy="loading">
        <p v-if="loading" role="status">正在加载第 {{ page }} 页…</p>
        <p v-else-if="previewError" class="chat-file-error" role="alert">{{ previewError }}</p>
        <img v-else-if="previewUrl" :src="previewUrl" :alt="'幻灯片第 ' + page + ' 页'" />
      </div>
      <template #footer>
        <p v-if="downloadError" class="chat-file-error" role="alert">{{ downloadError }}</p>
        <div class="chat-file-preview-footer">
          <div v-if="slideCount" class="chat-file-pages">
            <el-button :icon="ArrowLeft" aria-label="上一页" :disabled="page <= 1" @click="page--" />
            <span>{{ page }} / {{ slideCount }}</span>
            <el-button :icon="ArrowRight" aria-label="下一页" :disabled="page >= slideCount" @click="page++" />
          </div>
          <el-button type="primary" :icon="Download" :loading="downloading" @click="download">下载 PPTX</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>
