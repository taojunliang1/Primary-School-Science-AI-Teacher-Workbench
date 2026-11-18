import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1', timeout: 8000 })
const session = token => ({ headers: { Authorization: 'Bearer ' + token } })

export const scheduleApi = {
  read: async token => (await api.get('/courses', session(token))).data,
  save: async (token, version, cells) => (await api.put('/courses', { version, cells }, session(token))).data,
  prepLinks: async token => (await api.get('/prep/links', session(token))).data,
  prepLessons: async token => (await api.get('/prep/lessons', session(token))).data,
  equipment: async (token, lessonId, signal) => (await api.post(`/prep/lessons/${lessonId}/equipment`, null, {
    ...session(token), signal, timeout: 100000,
  })).data.items,
}

export function courseType(slot) {
  if (!slot.text?.trim()) return 'empty'
  if (!slot.isClass) return 'event'
  if (slot.courseType === 'contest' || /无人机足球|竞赛|社团|集训/.test(slot.text)) return 'contest'
  return 'regular'
}

export function prepSlotKey(row, dayIndex) {
  const text = row.slots[dayIndex].text.trim()
  const encoded = btoa(String.fromCharCode(...new TextEncoder().encode(text)))
    .replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/, '')
  return `${dayIndex + 1}:${row.time.replace(/\D/g, '')}:${encoded}`
}

export function collectScheduleCells(rows) {
  return rows.flatMap(row => (row.slots || []).flatMap((slot, index) => slot.skip ? [] : [{
    day: index + 1,
    period: row.time,
    text: slot.text?.trim() || '',
    courseType: courseType(slot),
    important: Boolean(slot.important && slot.isClass && slot.text?.trim()),
  }]))
}

export function applyAccountSchedule(rows, cells) {
  const byPeriod = new Map(cells.map(cell => [`${cell.day}:${cell.period}`, cell]))
  for (const row of rows) {
    row.slots?.forEach((slot, index) => {
      if (slot.skip) return
      const cell = byPeriod.get(`${index + 1}:${row.time}`) || { text: '', courseType: 'empty', important: false }
      slot.text = cell.text
      slot.courseType = cell.courseType
      slot.isClass = cell.courseType === 'regular' || cell.courseType === 'contest'
      slot.important = cell.important
    })
  }
  return rows
}
