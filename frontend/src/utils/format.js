export const riskClass = (risk) =>
  ({ Low: 'badge badge-low', Medium: 'badge badge-med', High: 'badge badge-high' }[risk] || 'badge badge-info')

export const riskColor = (risk) =>
  ({ Low: '#34d399', Medium: '#fbbf24', High: '#f87171' }[risk] || '#6366f1')

export const pct = (x, digits = 1) => `${(Number(x) * 100).toFixed(digits)}%`
export const num = (x, digits = 2) => Number(x).toFixed(digits)
export const minutes = (m) => (m >= 60 ? `${Math.floor(m / 60)}h ${m % 60 ? `${m % 60}m` : ''}`.trim() : `${m}m`)
export const initials = (name = '') =>
  name.split(' ').filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join('') || 'CP'

export const STUDY_TIME_LABEL = { 1: '< 2 h / week', 2: '2-5 h / week', 3: '5-10 h / week', 4: '> 10 h / week' }


// --- multi-subject helpers (upgrade) --------------------------------------- //
export const trendArrow = (direction) =>
  ({ up: '\u2191', down: '\u2193', flat: '\u2192' }[direction] || '\u2192')

export const trendColor = (direction) =>
  ({ up: '#34d399', down: '#f87171', flat: '#9aa6c4' }[direction] || '#9aa6c4')

export const severityClass = (severity) =>
  ({ high: 'badge badge-high', medium: 'badge badge-med', low: 'badge badge-low' }[severity]
    || 'badge badge-info')

export const percent = (value, digits = 0) =>
  value === null || value === undefined ? '-' : `${Number(value).toFixed(digits)}%`
