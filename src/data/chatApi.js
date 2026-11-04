import axios from 'axios'

export async function requestChatReply({ messages, model, token, signal }) {
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
  const { data } = await axios.post('/api/v1/chat/completions', { model, messages: context }, {
    headers: { Authorization: 'Bearer ' + token },
    signal,
    timeout: 85000,
  })
  return data
}
