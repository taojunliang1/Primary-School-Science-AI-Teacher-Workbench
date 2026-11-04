import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1', timeout: 8000 })
const config = (token, params) => ({ headers: { Authorization: 'Bearer ' + token }, params })

export const todoApi = {
  login: async credentials => (await api.post('/auth/login', credentials)).data,
  me: async token => (await api.get('/auth/me', config(token))).data,
  list: async (token, date) => (await api.get('/todos', config(token, { date }))).data,
  create: async (token, data) => (await api.post('/todos', data, config(token))).data,
  update: async (token, id, data) => (await api.patch('/todos/' + id, data, config(token))).data,
  remove: async (token, id) => api.delete('/todos/' + id, config(token)),
  complete: async (token, date) => (await api.post('/todos/complete', null, config(token, { date }))).data,
  clearCompleted: async (token, date) => (await api.delete('/todos/completed', config(token, { date }))).data,
  import: async (token, items) => (await api.post('/todos/import', { items }, config(token))).data,
}

export function apiMessage(error) {
  if (!error.response) return '无法连接后端，请确认 FastAPI 已启动后重试。'
  const detail = error.response.data?.detail
  return typeof detail === 'string' ? detail : '请求失败，请稍后重试。'
}
