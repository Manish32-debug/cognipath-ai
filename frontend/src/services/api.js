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

  // --- question bank, practice, resources and sample papers ---
  practiceConfig: () => api.get('/api/practice/config').then((r) => r.data),
  recommendedPractice: (id) => api.get(`/api/practice/recommended/${id}`).then((r) => r.data),
  startPractice: (id, payload) =>
    api.post(`/api/practice/start?student_id=${encodeURIComponent(id)}`, payload).then((r) => r.data),
  submitPractice: (payload) => api.post('/api/practice/submit', payload).then((r) => r.data),
  practiceHistory: (id) => api.get(`/api/practice/history/${id}`).then((r) => r.data),
  practicePerformance: (id) => api.get(`/api/practice/performance/${id}`).then((r) => r.data),

  questions: (params = {}) =>
    api.get('/api/questions', { params }).then((r) => r.data),
  bankSummary: () => api.get('/api/questions/bank-summary').then((r) => r.data),
  createQuestion: (payload) => api.post('/api/questions', payload).then((r) => r.data),
  updateQuestion: (id, payload) => api.put(`/api/questions/${id}`, payload).then((r) => r.data),
  deleteQuestion: (id) => api.delete(`/api/questions/${id}`).then((r) => r.data),

  resources: (params = {}) => api.get('/api/resources', { params }).then((r) => r.data),
  recommendedResources: (id) =>
    api.get(`/api/resources/recommended/${id}`).then((r) => r.data),
  createResource: (payload) => api.post('/api/resources', payload).then((r) => r.data),
  updateResource: (id, payload) => api.put(`/api/resources/${id}`, payload).then((r) => r.data),
  deleteResource: (id) => api.delete(`/api/resources/${id}`).then((r) => r.data),

  samplePapers: (params = {}) => api.get('/api/sample-papers', { params }).then((r) => r.data),
  // Blob URLs are built here so the Authorization interceptor still applies -
  // a plain <a href> would hit the endpoint without the bearer token.
  samplePaperBlob: (id) =>
    api.get(`/api/sample-papers/${id}/file`, { responseType: 'blob' }).then((r) => r.data),
  uploadSamplePaper: (formData) =>
    api.post('/api/sample-papers', formData).then((r) => r.data),
  deleteSamplePaper: (id) => api.delete(`/api/sample-papers/${id}`).then((r) => r.data),

  practiceAnalytics: () => api.get('/api/teacher/practice-analytics').then((r) => r.data),
  // --- multi-subject academic records (upgrade) --------------------------- //
  subjects: () => api.get('/api/subjects').then((r) => r.data),
  createSubject: (payload) => api.post('/api/subjects', payload).then((r) => r.data),
  subjectConcepts: (id) => api.get(`/api/subjects/${id}/concepts`).then((r) => r.data),
  subjectGraph: (id) => api.get(`/api/subjects/${id}/knowledge-graph`).then((r) => r.data),
  academics: (studentId) => api.get(`/api/students/${studentId}/academics`).then((r) => r.data),
  subjectDetail: (studentId, subjectId) =>
    api.get(`/api/students/${studentId}/academics/${subjectId}`).then((r) => r.data),
  subjectPrediction: (studentId, subjectId) =>
    api.get(`/api/students/${studentId}/academics/${subjectId}/prediction`).then((r) => r.data),
  earlyWarnings: (studentId) =>
    api.get(`/api/students/${studentId}/early-warnings`).then((r) => r.data),
  assessments: (subjectId) =>
    api.get('/api/assessments', { params: subjectId ? { subject_id: subjectId } : {} })
      .then((r) => r.data),
  createAssessment: (payload) => api.post('/api/assessments', payload).then((r) => r.data),
  recordResult: (assessmentId, payload) =>
    api.post(`/api/assessments/${assessmentId}/results`, payload).then((r) => r.data),
  subjectAnalytics: () => api.get('/api/teacher/subject-analytics').then((r) => r.data),
  mlProvenance: () => api.get('/api/ml/provenance').then((r) => r.data),
}

export default api
