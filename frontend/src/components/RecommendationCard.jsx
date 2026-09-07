import { Card } from './Card.jsx'
import { minutes, riskClass } from '../utils/format.js'

const ICON = { video: '\u25B6', article: '\u2261', practice: '\u2713', revision: '\u21BA' }

export default function RecommendationCard({ recommendations }) {
  const items = recommendations?.items || []
  const s = recommendations?.scoring

  return (
    <Card title="Personalised recommendations"
      subtitle={s
        ? `Priority = ${s.root_cause_weight} root-cause + ${s.gap_weight} mastery gap + ${s.downstream_weight} downstream impact + ${s.risk_weight} predicted risk.`
        : undefined}>
      {!items.length && <p className="small">{recommendations?.message || 'Nothing to recommend right now.'}</p>}

      <div className="stack">
        {items.map((item) => (
          <div key={item.concept} className="card" style={{ background: 'var(--bg-alt)', boxShadow: 'none' }}>
            <div className="between">
              <h3>Priority {item.priority}: {item.label}</h3>
              <span className="row" style={{ gap: '.4rem' }}>
                {item.is_root_cause && <span className="badge badge-root">root cause</span>}
                <span className={riskClass(item.risk)}>{Math.round(item.mastery)}% mastery</span>
              </span>
            </div>
            <p className="small" style={{ margin: '.45rem 0 .3rem' }}>{item.reason}</p>
            <p className="small" style={{ margin: 0 }}><b>Action:</b> {item.action}</p>

            <div className="stack" style={{ gap: '.35rem', marginTop: '.7rem' }}>
              {item.resources.map((r) => (
                <a key={r.url + r.title} href={r.url} target="_blank" rel="noreferrer"
                  className="between small"
                  style={{ padding: '.4rem .55rem', border: '1px solid var(--border)', borderRadius: 8 }}>
                  <span><span aria-hidden style={{ color: 'var(--brand-2)' }}>{ICON[r.type] || '\u2022'}</span> {r.title}</span>
                  <span className="tiny muted">{r.type} &middot; {minutes(r.minutes)}</span>
                </a>
              ))}
            </div>
            <div className="tiny muted" style={{ marginTop: '.5rem' }}>
              Estimated effort: {minutes(item.estimated_minutes)}
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
