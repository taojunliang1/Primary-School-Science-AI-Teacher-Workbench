<script setup>
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import texmath from 'markdown-it-texmath'
import katex from 'katex'
import 'katex/dist/contrib/mhchem'
import 'katex/dist/katex.min.css'
import DOMPurify from 'dompurify'
import { artifactReferencePattern } from '../data/chatApi'

const props = defineProps({ text: { type: String, required: true }, fileIds: { type: Array, default: () => [] } })
const markdown = new MarkdownIt({ html: false, breaks: true }).use(texmath, {
  engine: katex,
  delimiters: ['dollars', 'brackets'],
  katexOptions: { trust: false, throwOnError: false, maxSize: 10, maxExpand: 200 },
})
// 回复中的远程图片不自动加载，避免对话预览发起外部网络请求。
markdown.renderer.rules.image = (tokens, index) => markdown.utils.escapeHtml(tokens[index].content)
const safe = html => DOMPurify.sanitize(html, { ADD_TAGS: ['eq', 'eqn', 'eqno'] })

const blocks = computed(() => {
  const env = {}
  const tokens = markdown.parse(props.text, env)
  if (props.fileIds.length) {
    const fileIds = new Set(props.fileIds)
    for (const { children } of tokens) {
      let fileLink = false
      for (const token of children || []) {
        if (token.type === 'link_open') {
          const target = token.attrGet('href') || ''
          fileLink = /^(sandbox:|file:)/i.test(target)
            || Array.from(target.matchAll(artifactReferencePattern)).some(match => fileIds.has(match[1]))
          if (fileLink) {
            token.tag = 'span'
            token.attrs = null
          }
        } else if (fileLink && token.type === 'link_close') {
          token.tag = 'span'
          fileLink = false
        } else if (token.type === 'text' || token.type === 'code_inline') {
          token.content = token.content.replace(artifactReferencePattern,
            (match, id) => fileIds.has(id) ? '见下方文件卡片' : match)
        }
      }
    }
  }
  const result = []
  let start = 0
  const addHtml = end => {
    if (end > start) result.push({ html: safe(markdown.renderer.render(tokens.slice(start, end), markdown.options, env)) })
  }
  for (let i = 0; i < tokens.length; i++) {
    if (tokens[i].type !== 'table_open' || tokens[i].level !== 0) continue
    addHtml(i)
    const columns = []
    const rows = []
    let inHeader = false
    let row
    for (i++; i < tokens.length && tokens[i].type !== 'table_close'; i++) {
      const token = tokens[i]
      if (token.type === 'thead_open') inHeader = true
      if (token.type === 'thead_close') inHeader = false
      if (token.type === 'tr_open') row = []
      if (token.type === 'inline') {
        row.push({ text: token.content, html: safe(markdown.renderer.renderInline(token.children, markdown.options, env)) })
      }
      if (token.type === 'tr_close') {
        if (inHeader) columns.push(...row)
        else rows.push(row)
      }
    }
    result.push({ columns, rows })
    start = i + 1
  }
  addHtml(tokens.length)
  return result
})
</script>

<template>
  <div class="chat-markdown">
    <template v-for="(block, index) in blocks" :key="index">
      <div v-if="block.html !== undefined" class="chat-rich-text" v-html="block.html" />
      <el-table v-else :data="block.rows" stripe border size="small" class="chat-data-table">
        <el-table-column v-for="(column, col) in block.columns" :key="col" :label="column.text" min-width="138">
          <template #header><span v-html="column.html" /></template>
          <template #default="{ row }"><span v-html="row[col]?.html || ''" /></template>
        </el-table-column>
      </el-table>
    </template>
  </div>
</template>
