import { Link, useOutletContext } from 'react-router-dom'
import { Bar, StatCard, Card } from '../../components/Card.jsx'
import { GradeTrendChart } from '../../charts/PerformanceChart.jsx'
import SHAPChart from '../../charts/SHAPChart.jsx'
import { minutes, num, pct, riskColor } from '../../utils/format.js'

export default function Overview() {
  const { data } = useOutletContext()
  const { prediction, explanation, mastery, root_cause: rc, student, practice } = data
  const topRoot = rc.root_causes?.[0]
  const focus = practice?.recommended?.items?.slice(0, 2) || []
  const totals = practice?.totals
  const recent = practice?.recent_sessions || []

  return (
    <div className="stack">
      <div className="grid grid-4">
        <StatCard
          label="Predicted GPA"
          value={num(prediction.predicted_gpa)}
          suffix="/ 10"
          hint={`Model: ${prediction.models_used.gpa}`}
        />

        <StatCard
          label="Pass probability"
          value={pct(prediction.pass_probability, 0)}
          hint="Final grade >= 10 / 20"
        />

        <StatCard
          label="Academic risk"
          value={prediction.risk_tier}
          tone={riskColor(prediction.risk_tier)}
          hint={`Model: ${prediction.models_used.risk}`}
        />

        <StatCard
          label="Overall mastery"
          value={mastery.overall ?? '-'}
          suffix="%"
          hint={`Source: ${mastery.source}`}
        />
      </div>

      <div className="grid grid-2">
        <Card
          title="Grade progression"
          subtitle="AI model view: original G1/G2 inputs followed by the predicted final outcome. Six academic assessments are tracked separately."
        >
          <GradeTrendChart
            features={student.features}
            predictedGpa={prediction.predicted_gpa}
          />
        </Card>

        <Card
          title="Top prediction drivers"
          subtitle={`SHAP on the ${explanation.model} model (${explanation.units}).`}
        >
          <SHAPChart
            contributions={explanation.top_contributions.slice(0, 7)}
            units={explanation.units}
            height={250}
          />
        </Card>
      </div>

      {topRoot && (
        <Card
          title="Most likely prerequisite gap"
          right={
            <span className="badge badge-root">
              {topRoot.label}
            </span>
          }
        >
          <p className="small" style={{ margin: 0 }}>
            {topRoot.reasoning}
          </p>
        </Card>
      )}

      {focus.length > 0 && (
        <Card
          title="AI recommended for you"
          subtitle="Study the material, then practise the concept. Both are selected from your current learning state."
          right={
            <Link className="btn btn-sm" to="/app/practice">
              All recommendations
            </Link>
          }
        >
          <div className="grid grid-2">
            {focus.map((item) => (
              <div
                key={item.concept}
                className="card"
                style={{
                  background: 'var(--bg-alt)',
                  boxShadow: 'none',
                }}
              >
                <div className="between">
                  <h3>{item.label}</h3>

                  {item.is_root_cause && (
                    <span className="badge badge-root">
                      root cause
                    </span>
                  )}
                </div>

                <div
                  className="tiny muted"
                  style={{ margin: '.2rem 0 .4rem' }}
                >
                  {Math.round(item.mastery)}% mastery
                </div>

                <Bar value={item.mastery} />

                <p
                  className="small"
                  style={{ margin: '.6rem 0' }}
                >
                  {item.reason}
                </p>

                <div className="row wrap">
                  <Link
                    className="btn btn-sm"
                    to="/app/resources"
                  >
                    Study material
                    {item.resources?.length
                      ? ` (${minutes(
                          item.resources.reduce(
                            (a, r) => a + r.estimated_minutes,
                            0
                          )
                        )})`
                      : ''}
                  </Link>

                  <Link
                    className="btn btn-primary btn-sm"
                    to="/app/practice"
                  >
                    Practise{' '}
                    {item.available_questions ||
                      item.recommended_questions}{' '}
                    {item.difficulty} questions
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {totals?.attempted > 0 && (
        <div className="grid grid-2">
          <Card
            title="Practice so far"
            right={
              <Link
                className="btn btn-sm"
                to="/app/practice-history"
              >
                Full history
              </Link>
            }
          >
            <div className="grid grid-3">
              <StatCard
                label="Attempted"
                value={totals.attempted}
              />

              <StatCard
                label="Accuracy"
                value={totals.accuracy}
                suffix="%"
                tone={
                  totals.accuracy >= 70
                    ? 'var(--good)'
                    : totals.accuracy >= 50
                      ? 'var(--warn)'
                      : 'var(--bad)'
                }
              />

              <StatCard
                label="Score"
                value={totals.score}
                suffix={`/ ${totals.max_score}`}
              />
            </div>
          </Card>

          <Card title="Recent sessions">
            <div
              className="stack"
              style={{ gap: '.35rem' }}
            >
              {recent.map((s) => (
                <div
                  key={s.session_id}
                  className="between small"
                  style={{
                    padding: '.4rem .55rem',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                  }}
                >
                  <span>
                    {s.label || s.concept || 'Mixed'}
                  </span>

                  <span className="tiny muted mono">
                    {s.correct}/{s.questions} &middot; {s.accuracy}%
                  </span>
                </div>
              ))}

              {!recent.length && (
                <span className="tiny muted">
                  No completed sessions yet.
                </span>
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}