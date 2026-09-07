import { Card } from './Card.jsx'
import { minutes } from '../utils/format.js'

export default function StudyPlan({ plan }) {
  const days = plan?.days || []
  return (
    <Card title="Weekly study plan"
      subtitle={plan?.budget_inputs
        ? `Budget derived from study time (${plan.budget_inputs.studytime}/4), free time (${plan.budget_inputs.freetime}/5) and ${plan.budget_inputs.risk_tier} risk.`
        : undefined}
      right={plan?.weekly_minutes && <span className="chip">{minutes(plan.weekly_minutes)} / week</span>}>
      {plan?.note && <div className="notice" style={{ marginBottom: '1rem' }}>{plan.note}</div>}

      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
        {days.map((d) => (
          <div key={d.day} className="card" style={{ background: 'var(--bg-alt)', boxShadow: 'none', padding: '.8rem' }}>
            <div className="between" style={{ marginBottom: '.5rem' }}>
              <strong className="small">{d.day}</strong>
              <span className="tiny muted">
                {d.sessions.length ? minutes(d.sessions.reduce((a, s) => a + s.minutes, 0)) : 'rest'}
              </span>
            </div>
            {!d.sessions.length && <div className="tiny muted">No scheduled session</div>}
            {d.sessions.map((s, i) => (
              <div key={i} style={{ marginBottom: '.55rem' }}>
                <div className="small">
                  {s.is_root_cause && <span className="badge badge-root" style={{ marginRight: '.35rem' }}>root</span>}
                  {s.focus}
                </div>
                <div className="tiny muted">{minutes(s.minutes)}{s.resource ? ` \u00B7 ${s.resource.title}` : ''}</div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </Card>
  )
}
