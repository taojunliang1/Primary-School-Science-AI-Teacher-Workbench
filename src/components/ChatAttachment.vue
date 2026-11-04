<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { Document, Picture } from '@element-plus/icons-vue'

const props = defineProps({ attachment: { type: Object, required: true }, compact: Boolean })
const url = ref('')
const release = () => { if (url.value) URL.revokeObjectURL(url.value) }
watch(() => props.attachment.file, file => {
  release()
  url.value = file instanceof Blob ? URL.createObjectURL(file) : ''
}, { immediate: true })
onBeforeUnmount(release)
</script>

<template>
  <a v-if="url" class="chat-attachment" :class="{ compact }" :href="url" :download="attachment.name" :title="'下载附件：' + attachment.name">
    <img v-if="attachment.image" :src="url" :alt="attachment.name" />
    <el-icon v-else><Document /></el-icon>
    <span>{{ attachment.name }}</span>
  </a>
  <span v-else class="chat-attachment compact"><el-icon><Picture /></el-icon>{{ attachment.name }}</span>
</template>
