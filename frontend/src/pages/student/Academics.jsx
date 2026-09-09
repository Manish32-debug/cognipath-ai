import { Link, useOutletContext } from 'react-router-dom'
import { Card, StatCard, Bar } from '../../components/Card.jsx'
import { Async, EmptyState } from '../../components/Loader.jsx'
import { useApi } from '../../hooks/useApi.js'
import { endpoints } from '../../services/api.js'
import {
  num, percent, riskClass, riskColor, severityClass, trendArrow, trendColor,
} from '../../utils/format.js'

/** Academic Overview: every subject, its current level, trend and risk, with the
 *  early-warning list underneath. All values come from the API - the page does
 *  no arithmetic of its own. */
export default function Academics() {
  const { studentId } = useOutletContext()
  const academics = useApi(() => endpoints.academics(studentId), [studentId],
    { enabled: Boolean(studentId) })
  const warnings = useApi(() => endpoints.earlyWarnings(studentId), [studentId],
    { enabled: Boolean(studentId) })

  return (
    <div className="stack">
      <Async loading={academics.loading} error={academics.error} onRetry={academics.reload}
        height={140} label="Loading assessment history and detecting trends...">
        {academics.data && (
          academics.data.subjects.length === 0
            ? <EmptyState title="No assessment results yet"
                hint={academics.data.message || 'Assessment marks appear here once a teacher records them.'} />
            : (
              <>
                <div className="grid grid-4">
                  <StatCard label="Subjects tracked" value={academics.data.overall.subjects_tracked} />
                  <StatCard label="Average across subjects"
                    value={percent(academics.data.overall.average_percentage)} />
                  <StatCard label="High-risk subjects"
                    value={academics.data.overall.risk_distribution.High}
                    tone={academics.data.overall.risk_distribution.High > 0 ? riskColor('High') : undefined} />
                  <StatCard label="Predicted GPA"
                    value={academics.data.ml_prediction?.prediction
                      ? num(academics.data.ml_prediction.prediction.predicted_gpa) : '-'}
                    suffix="/ 10"
                    hint="ML model, driven by assessment history" />
                </div>

                <Card title="Academic overview"
                  subtitle="Current level is the weighted average of the most recent assessments. Click a subject for its full analysis.">
                  <table>
                    <thead>
                      <tr>
                        <th>Subject</th><th>Current</th><th>Average</th>
                        <th>Assessments</th><th>Trend</th><th>Risk</th>
                      </tr>
                    </thead>
                    <tbody>
                      {academics.data.subjects.map((s) => (
                        <tr key={s.subject_id}>
                          <td>
                            <Link to={`/app/academics/${s.subject_id}`} style={{ color: 'var(--brand-2)' }}>
                              {s.subject_name}
                            </Link>
                          </td>
                          <td style={{ minWidth: 130 }}>
                            <Bar value={s.current || 0}
                              color={s.current < 50 ? '#f87171' : s.current < 70 ? '#fbbf24' : '#34d399'} />
                            <span className="tiny mono muted">{percent(s.current)}</span>
                          </td>
                          <td className="mono">{percent(s.average)}</td>
                          <td className="mono">{s.n_assessments}</td>
                          <td>
                            <span style={{ color: trendColor(s.direction) }} aria-hidden>
                              {trendArrow(s.direction)}
                            </span>{' '}
                            <span className="small">{s.trend}</span>
                            <div className="tiny muted">{s.slope > 0 ? '+' : ''}{s.slope} pts / assessment</div>
                          </td>
                          <td>
                            <span className={riskClass(s.risk)}>{s.risk}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Card>

                {academics.data.ml_prediction?.prediction && (
                  <Card title="Prediction from your assessment history"
                    subtitle={`Source: ${academics.data.ml_prediction.source.replace(/_/g, ' ')}`}>
                    <div className="grid grid-3">
                      <StatCard label="Predicted GPA"
                        value={num(academics.data.ml_prediction.prediction.predicted_gpa)} suffix="/ 10" />
                      <StatCard label="Pass probability"
                        value={percent(academics.data.ml_prediction.prediction.pass_probability * 100)} />
                      <StatCard label="Risk tier"
                        value={academics.data.ml_prediction.prediction.risk_tier}
                        tone={riskColor(academics.data.ml_prediction.prediction.risk_tier)} />
                    </div>
                    {academics.data.ml_prediction.derived_inputs && (
                      <div className="tiny muted" style={{ marginTop: '.6rem' }}>
                        Built from {academics.data.ml_prediction.derived_inputs.n_assessments} assessment
                        positions: earlier average {percent(academics.data.ml_prediction.derived_inputs.earlier_average_pct)},
                        recent average {percent(academics.data.ml_prediction.derived_inputs.recent_average_pct)}.
                      </div>
                    )}
                    <div className="notice" style={{ marginTop: '.7rem' }}>
                      {academics.data.ml_prediction.note}
                    </div>
                  </Card>
                )}
              </>
            )
        )}
      </Async>

      <Async loading={warnings.loading} error={warnings.error} onRetry={warnings.reload}
        label="Checking for early warning signs...">
        {warnings.data && (
          <Card title="Early warning"
            subtitle="Deterioration detected before it becomes a fail. Each warning shows the evidence that triggered it."
            right={warnings.data.n_warnings > 0
              ? <span className={severityClass(warnings.data.highest_severity)}>
                  {warnings.data.n_warnings} active
                </span>
              : <span className="badge badge-low">all clear</span>}>
            {warnings.data.warnings.length === 0
              ? <p className="small">{warnings.data.message}</p>
              : (
                <div className="stack">
                  {warnings.data.warnings.map((w) => (
                    <div key={w.subject_id} className="card"
                      style={{ background: 'var(--bg-alt)', boxShadow: 'none' }}>
                      <div className="between">
                        <div className="row wrap">
                          <strong>{w.subject_name}</strong>
                          <span className={severityClass(w.severity)}>{w.severity} severity</span>
                          <span className="chip">{w.trend}</span>
                        </div>
                        <Link to={`/app/academics/${w.subject_id}`} className="btn btn-sm">
                          Open subject
                        </Link>
                      </div>

                      <div className="tiny mono muted" style={{ margin: '.5rem 0' }}>
                        {w.assessment_names.map((n, i) => `${n}: ${w.series[i]}%`).join('  \u2192  ')}
                      </div>

                      <div className="small"><b>Why am I at risk?</b> {w.why_at_risk}</div>

                      {w.likely_root_cause && (
                        <div className="small" style={{ marginTop: '.4rem' }}>
                          <b>Likely root cause:</b> {w.likely_root_cause.label}{' '}
                          ({percent(w.likely_root_cause.mastery)} mastery)
                          <div className="tiny muted">{w.likely_root_cause.reasoning}</div>
                        </div>
                      )}

                      <div style={{ marginTop: '.5rem' }}>
                        <div className="stat-label">What should I do next?</div>
                        <ol className="small" style={{ margin: '.3rem 0 0 1rem', color: 'var(--muted)' }}>
                          {w.what_to_do_next.map((step, i) => <li key={i}>{step}</li>)}
                        </ol>
                      </div>
                    </div>
                  ))}
                </div>
              )}
          </Card>
        )}
      </Async>
    </div>
  )
}
