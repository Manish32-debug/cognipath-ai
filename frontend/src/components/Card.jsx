import { riskClass } from '../utils/format.js'

export function Card({ title, subtitle, right, children, className = '' }) {
  return (
    <section className={`card fade-in ${className}`}>
      {(title || right) && (
        <div className="between" style={{ marginBottom: subtitle ? '.15rem' : '.7rem' }}>
          {title && <h3>{title}</h3>}
          {right}
        </div>
      )}
      {subtitle && <div className="card-sub">{subtitle}</div>}
      {children}
    </section>
  )
}

export function StatCard({ label, value, suffix, hint, tone }) {
  return (
    <div className="card fade-in">
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={tone ? { color: tone } : undefined}>
        {value}
        {suffix && <span style={{ fontSize: '1rem', color: 'var(--muted)' }}> {suffix}</span>}
      </div>
      {hint && <div className="tiny muted">{hint}</div>}
    </div>
  )
}

export function RiskBadge({ risk }) {
  return <span className={riskClass(risk)}>{risk} risk</span>
}

export function Bar({ value, color = 'var(--brand)' }) {
  return (
    <div className="bar-track">
      <div className="bar-fill" style={{ width: `${Math.max(0, Math.min(100, value))}%`, background: color }} />
    </div>
  )
}
