import { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { Bar, Card } from '../../components/Card.jsx'
import { Async, EmptyState } from '../../components/Loader.jsx'
import { useApi } from '../../hooks/useApi.js'
import { endpoints } from '../../services/api.js'
import { minutes, riskClass } from '../../utils/format.js'

const ICON = { Video: '\u25B6', Article: '\u2261', Notes: '\u25A4', PDF: '\u2637', Exercise: '\u2713' }
const TYPES = ['Video', 'Article', 'Notes', 'PDF', 'Exercise']

function ResourceRow({ r }) {
  const body = (
    <>
      <span>
        <span aria-hidden style={{ color: 'var(--brand-2)' }}>{ICON[r.resource_type] || '\u2022'}</span>
        {' '}{r.title}
        {r.description && <div className="tiny muted">{r.description}</div>}
      </span>
      <span className="tiny muted" style={{ whiteSpace: 'nowrap' }}>
        {r.resource_type} &middot; {r.difficulty} &middot; {minutes(r.estimated_minutes)}
      </span>
    </>
  )
  const style = { padding: '.5rem .6rem', border: '1px solid var(--border)', borderRadius: 8 }
  return r.url
    ? <a className="between small" style={style} href={r.url} target="_blank" rel="noreferrer">{body}</a>
    : <div className="between small" style={style}>{body}</div>
}

export default function Resources() {
  const { studentId } = useOutletContext()
  const [type, setType] = useState('')

  const rec = useApi(() => endpoints.recommendedResources(studentId), [studentId],
    { enabled: Boolean(studentId) })
  const all = useApi(() => endpoints.resources(type ? { resource_type: type } : {}), [type])

  return (
    <div className="stack">
      <Card title="AI recommended resources"
        subtitle="Selected by concept priority, not by popularity. Every entry explains why it was chosen.">
        <Async loading={rec.loading} error={rec.error} onRetry={rec.reload} height={160}
          label="Matching resources to your weakest prerequisites...">
          {rec.data && (rec.data.items?.length ? (
            <div className="stack">
              {rec.data.items.map((item) => (
                <div key={item.concept} className="card" style={{ background: 'var(--bg-alt)', boxShadow: 'none' }}>
                  <div className="between">
                    <h3>{item.label}</h3>
                    <span className="row" style={{ gap: '.4rem' }}>
                      {item.is_root_cause && <span className="badge badge-root">root cause</span>}
                      <span className={riskClass(item.mastery < 40 ? 'High' : item.mastery < 60 ? 'Medium' : 'Low')}>
                        {Math.round(item.mastery)}% mastery
                      </span>
                    </span>
                  </div>
                  <Bar value={item.mastery} />
                  <p className="small" style={{ margin: '.6rem 0' }}>{item.reason}</p>
                  <div className="stack" style={{ gap: '.35rem' }}>
                    {item.resources.length
                      ? item.resources.map((r) => <ResourceRow key={r.resource_id} r={r} />)
                      : <span className="tiny muted">No library resources mapped to this concept yet.</span>}
                  </div>
                  <div className="tiny muted" style={{ marginTop: '.6rem' }}>
                    Estimated study time {minutes(item.estimated_minutes)} &middot; then{' '}
                    {item.practice.recommended_questions} {item.practice.difficulty} questions
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No resources recommended"
              hint={rec.data.message || 'Every concept is at or above the mastery target.'} />
          ))}
        </Async>
      </Card>

      <Card title="Full resource library"
        right={
          <select value={type} onChange={(e) => setType(e.target.value)} style={{ width: 160 }}>
            <option value="">All types</option>
            {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        }>
        <Async loading={all.loading} error={all.error} onRetry={all.reload} height={140}
          label="Loading the resource library...">
          {all.data && (all.data.count ? (
            <div className="stack" style={{ gap: '.35rem' }}>
              {all.data.resources.map((r) => <ResourceRow key={r.resource_id} r={r} />)}
            </div>
          ) : <EmptyState title="No resources" hint="Nothing matches this filter yet." />)}
        </Async>
      </Card>
    </div>
  )
}
