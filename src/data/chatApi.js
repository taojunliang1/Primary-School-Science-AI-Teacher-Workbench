import axios from 'axios'

export async function encodeChatImage(file, maxDimension = 1200) {
  const bitmap = await createImageBitmap(file)
  try {
    const scale = Math.min(1, maxDimension / Math.max(bitmap.width, bitmap.height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(bitmap.width * scale))
    canvas.height = Math.max(1, Math.round(bitmap.height * scale))
    const context = canvas.getContext('2d', { alpha: false })
    context.fillStyle = '#fff'
    context.fillRect(0, 0, canvas.width, canvas.height)
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    return canvas.toDataURL('image/jpeg', 0.82).split(',')[1]
  } finally {
    bitmap.close()
  }
}

export async function requestChatReply({ messages, model, token, signal, webSearch, onEvent }) {
  // Keep recent text turns only, excluding historical demo replies and local attachments.
  const context = []
  let remaining = 48000
  for (const message of messages.slice(-20).reverse()) {
    if (message.role === 'assistant' && !message.providerModel) continue
    const content = message.text.trim().slice(0, 24000)
    if (!content) continue
    if (content.length > remaining) break
    context.unshift({ role: message.role, content })
    remaining -= content.length
  }
  const images = await Promise.all((messages.at(-1).attachments || [])
    .filter(attachment => attachment.image && attachment.file)
    .map(attachment => encodeChatImage(attachment.file).catch(() => {
      throw new Error('图片无法读取，请换一张 JPEG、PNG、WebP 或 GIF 图片。')
    })))
  const response = await fetch('/api/v1/chat/stream', {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, messages: context, enable_skills: true, web_search: webSearch, images }),
    signal,
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || '对话服务暂不可用，请稍后重试。')
  }
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) throw new Error('回复中断，请重试。')
      buffer += value
      const lines = buffer.split('\n')
      buffer = lines.pop()
      for (const line of lines) {
        if (!line) continue
        const event = JSON.parse(line)
        if (event.type === 'error') throw new Error(event.message)
        if (event.type === 'done') return event.reply
        onEvent(event)
      }
    }
  } finally {
    await reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}

export async function fetchChatSkills({ token }) {
  const { data } = await axios.get('/api/v1/chat/skills', {
    headers: { Authorization: 'Bearer ' + token },
    timeout: 15000,
  })
  return data
}

const artifactPath = id => '/api/v1/chat/artifacts/' + encodeURIComponent(id)
export const artifactReferencePattern = /(?:https?:\/\/(?:localhost|127\.0\.0\.1)(?::\d+)?)?\/api\/v1\/chat\/artifacts\/([a-f0-9]{32})(?![a-f0-9])/g

export async function lookupChatArtifacts({ ids, token, signal }) {
  const { data } = await axios.post('/api/v1/chat/artifacts/lookup', ids, {
    headers: { Authorization: 'Bearer ' + token },
    signal,
    timeout: 15000,
  })
  return data
}

export async function prepareChatArtifactDownload({ artifactId, token }) {
  const path = artifactPath(artifactId)
  const { data } = await axios.post(path + '/download', null, {
    headers: { Authorization: 'Bearer ' + token },
    timeout: 15000,
  })
  if (data.url !== path) throw new Error('下载地址无效')
  return path
}

export async function previewChatArtifact({ artifactId, token, page, signal }) {
  const response = await fetch(artifactPath(artifactId) + '/preview?' + new URLSearchParams({ slide: page }), {
    headers: { Authorization: 'Bearer ' + token },
    signal,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || '暂时无法预览，可直接下载文件。')
  }
  return { image: await response.blob(), slideCount: Number(response.headers.get('X-Slide-Count')) }
}
