import { Card } from './Card.jsx'
import { riskClass } from '../utils/format.js'

/** Root-cause diagnosis. Wording is deliberately hedged ("likely", "probable"):
 *  this is graph inference over a curriculum model, not proven causality. */
export default function RootCausePanel({ analysis }) {
  const roots = analysis?.root_causes || []
  const weak = analysis?.weak_concepts || []

  return (
    <Card title="Root-cause analysis"
      subtitle="Backward traversal of the prerequisite graph, weighted by mastery gap, edge strength and distance.">
      {!weak.length && <p className="small">No concept is below the 60% weakness threshold for this student.</p>}

      {weak.length > 0 && (
        <div className="row wrap" style={{ marginBottom: '1rem' }}>
          <span className="small muted">Weak concepts:</span>
          {weak.map((w) => (
            <span key={w.concept} className={riskClass(w.risk)}>
              {w.label} {Math.round(w.mastery)}%
            </span>
          ))}
        </div>
      )}

      <div className="stack">
        {roots.map((r, i) => (
          <div key={r.concept} className="card" style={{ background: 'var(--bg-alt)', boxShadow: 'none' }}>
            <div className="between">
              <h3>
                <span className="badge badge-root">#{i + 1} likely root cause</span>{' '}
                {r.label}
              </h3>
              <span className="mono tiny muted">score {r.root_score}</span>
            </div>
            <p className="small" style={{ margin: '.5rem 0' }}>{r.reasoning}</p>

            <div className="row wrap tiny muted" style={{ gap: '1rem' }}>
              <span>own gap <b className="mono">{r.own_gap}</b></span>
              <span>downstream pressure <b className="mono">{r.downstream_pressure}</b></span>
              <span>upstream clearance <b className="mono">{r.upstream_clearance}</b></span>
            </div>

            {r.affected_concepts?.length > 0 && (
              <div style={{ marginTop: '.7rem' }}>
                <div className="tiny muted" style={{ marginBottom: '.3rem' }}>Reasoning paths</div>
                {r.affected_concepts.slice(0, 3).map((a) => (
                  <div key={a.concept} className="tiny mono" style={{ color: 'var(--muted)' }}>
                    {a.path_labels.join('  \u2192  ')} &nbsp;
                    <span style={{ color: 'var(--bad)' }}>({Math.round(a.mastery)}%)</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {analysis?.disclaimer && <div className="notice" style={{ marginTop: '1rem' }}>{analysis.disclaimer}</div>}
    </Card>
  )
}
