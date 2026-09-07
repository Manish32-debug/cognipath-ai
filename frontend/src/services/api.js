import axios from 'axios'

// Base URL: empty in dev so Vite's proxy handles /api, explicit in production.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 30000,
})

export const TOKEN_KEY = 'cognipath_token'

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Normalise every backend/network failure into a single readable message so
// components never have to unpack an axios error themselves.
api.interceptors.response.use(
  (r) => r,
  (error) => {
    const status = error.response?.status
    let detail = error.response?.data?.detail
    if (Array.isArray(detail)) detail = detail.map((d) => `${d.loc?.slice(-1)}: ${d.msg}`).join(', ')
    if (!detail) {
      if (error.code === 'ECONNABORTED') detail = 'The request timed out.'
      else if (!error.response) detail = 'Cannot reach the API. Is the FastAPI server running on port 8000?'
      else if (status === 503) detail = 'Models are not trained yet. Run: python -m app.ml.train'
      else detail = `Request failed (HTTP ${status}).`
    }
    if (status === 401) localStorage.removeItem(TOKEN_KEY)
    return Promise.reject(Object.assign(new Error(detail), { status }))
  },
)

export const endpoints = {
  health: () => api.get('/api/health').then((r) => r.data),
  modelInfo: () => api.get('/api/model-info').then((r) => r.data),
  evaluation: () => api.get('/api/evaluation').then((r) => r.data),
  login: (username, password) => api.post('/api/auth/login', { username, password }).then((r) => r.data),
  register: (payload) => api.post('/api/auth/register', payload).then((r) => r.data),
  me: () => api.get('/api/auth/me').then((r) => r.data),
  dashboard: (id) => api.get(`/api/students/${id}/dashboard`).then((r) => r.data),
  mastery: (id) => api.get(`/api/students/${id}/mastery`).then((r) => r.data),
  updateMastery: (id, records) => api.put(`/api/students/${id}/mastery`, { records }).then((r) => r.data),
  knowledgeGraph: () => api.get('/api/knowledge-graph').then((r) => r.data),
  concepts: () => api.get('/api/concepts').then((r) => r.data),
  predict: (features) => api.post('/api/predict', features).then((r) => r.data),
  explain: (features, task = 'gpa') => api.post(`/api/explain?task=${task}`, features).then((r) => r.data),
  rootCause: (mastery) => api.post('/api/root-cause', { mastery }).then((r) => r.data),
  analytics: () => api.get('/api/teacher/analytics').then((r) => r.data),
  teacherStudent: (id) => api.get(`/api/teacher/student/${id}`).then((r) => r.data),
  createStudent: (payload) => api.post('/api/students', payload).then((r) => r.data),
}

export default api
