import { Card, RiskBadge } from './Card.jsx'
import { num, pct } from '../utils/format.js'

/** Model output panel. Every number here comes from the API response - the
 *  component does no arithmetic beyond formatting. */
export default function PredictionCard({ prediction }) {
  if (!prediction) return null
  const probs = prediction.risk_probabilities || {}
  return (
    <Card title="AI prediction"
      subtitle={`GPA: ${prediction.models_used.gpa} | Pass: ${prediction.models_used.pass} | Risk: ${prediction.models_used.risk}`}
      right={<RiskBadge risk={prediction.risk_tier} />}>
      <div className="grid grid-3" style={{ gap: '.9rem' }}>
        <div>
          <div className="stat-label">Predicted GPA</div>
          <div className="stat-value">{num(prediction.predicted_gpa)}<span className="muted" style={{ fontSize: '1rem' }}> / 10</span></div>
          <div className="tiny muted">Equivalent to {num(prediction.predicted_g3_equivalent)} / 20 on the source scale</div>
        </div>
        <div>
          <div className="stat-label">Pass probability</div>
          <div className="stat-value">{pct(prediction.pass_probability, 1)}</div>
          <div className="tiny muted">Classifier estimate of final grade &ge; 10 / 20</div>
        </div>
        <div>
          <div className="stat-label">Risk class probabilities</div>
          <div className="stack" style={{ gap: '.35rem', marginTop: '.4rem' }}>
            {Object.entries(probs).map(([k, v]) => (
              <div key={k} className="between tiny">
                <span className="muted">{k}</span>
                <span className="mono">{pct(v, 1)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="notice" style={{ marginTop: '1rem' }}>{prediction.interpretation}</div>
    </Card>
  )
}
