import {
  Bar as RBar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Card, StatCard } from '../../components/Card.jsx'
import { Async, EmptyState } from '../../components/Loader.jsx'
import { useApi } from '../../hooks/useApi.js'
import { endpoints } from '../../services/api.js'

const accuracyColor = (a) => (a >= 70 ? '#34d399' : a >= 50 ? '#fbbf24' : '#f87171')

function AccuracyChart({ rows }) {
  const data = rows.slice(0, 10).map((r) => ({
    name: r.label || r.concept,
    accuracy: r.average_accuracy,
  }))
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} layout="vertical" margin={{ left: 40 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis type="number" domain={[0, 100]} stroke="var(--muted)" fontSize={12} />
        <YAxis type="category" dataKey="name" width={140} stroke="var(--muted)" fontSize={11} />
        <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
          formatter={(v) => [`${v}%`, 'Average accuracy']} />
        <RBar dataKey="accuracy" radius={[0, 4, 4, 0]}>
          {data.map((d) => <Cell key={d.name} fill={accuracyColor(d.accuracy)} />)}
        </RBar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export default function PracticeAnalytics() {
  const { data, error, loading, reload } = useApi(() => endpoints.practiceAnalytics(), [])

  return (
    <Async loading={loading} error={error} onRetry={reload} height={160}
      label="Aggregating stored practice attempts...">
      {data && (
        <div className="stack">
          <div className="grid grid-4">
            <StatCard label="Questions in bank" value={data.totals.total_questions} />
            <StatCard label="Practice attempts" value={data.totals.total_attempts} />
            <StatCard label="Average accuracy" value={data.totals.average_accuracy} suffix="%"
              tone={accuracyColor(data.totals.average_accuracy)} />
            <StatCard label="Students practising" value={data.totals.students_practised} />
          </div>

          {!data.totals.total_attempts ? (
            <EmptyState title="No practice attempts yet"
              hint="Analytics appear once students complete practice sessions. Every figure here is aggregated from stored attempts - nothing is simulated." />
          ) : (
            <>
              <div className="grid grid-2">
                <Card title="Hardest concepts"
                  subtitle="Lowest average accuracy across all stored attempts.">
                  <AccuracyChart rows={data.concept_performance} />
                </Card>

                <Card title="Most attempted concepts">
                  <table>
                    <thead><tr><th>Concept</th><th>Attempts</th><th>Students</th><th>Accuracy</th></tr></thead>
                    <tbody>
                      {data.most_attempted_concepts.map((c) => (
                        <tr key={c.concept}>
                          <td>{c.label || c.concept}</td>
                          <td className="mono">{c.attempted}</td>
                          <td className="mono">{c.students}</td>
                          <td className="mono" style={{ color: accuracyColor(c.average_accuracy) }}>
                            {c.average_accuracy}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Card>
              </div>

              <Card title="Students struggling by concept"
                subtitle="Below 50% accuracy with at least three attempts on that concept.">
                {data.struggling_students.length ? (
                  <div className="stack">
                    {data.struggling_students.map((group) => (
                      <div key={group.concept}>
                        <div className="between" style={{ marginBottom: '.35rem' }}>
                          <b className="small">{group.label}</b>
                          <span className="chip">{group.students.length} student(s)</span>
                        </div>
                        <div className="row wrap">
                          {group.students.map((s) => (
                            <span key={s.student_id} className="chip">
                              {s.display_name || s.student_id} &middot; {s.accuracy}% ({s.attempted})
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="small muted">
                    No student is below the 50% threshold with enough attempts to judge.
                  </p>
                )}
              </Card>

              <Card title="Most attempted questions"
                subtitle="Low accuracy on a heavily attempted question usually means the question is unclear, not that the cohort is weak.">
                <div style={{ overflowX: 'auto' }}>
                  <table>
                    <thead>
                      <tr><th>Question</th><th>Concept</th><th>Difficulty</th>
                        <th>Attempts</th><th>Accuracy</th></tr>
                    </thead>
                    <tbody>
                      {data.most_attempted_questions.map((q) => (
                        <tr key={q.question_id}>
                          <td className="small" style={{ maxWidth: 380 }}>{q.question_text}</td>
                          <td className="small">{q.label || q.concept}</td>
                          <td className="tiny">{q.difficulty}</td>
                          <td className="mono">{q.attempted}</td>
                          <td className="mono" style={{ color: accuracyColor(q.accuracy) }}>{q.accuracy}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </>
          )}

          <Card title="Question bank coverage"
            subtitle="Concepts with no questions cannot be practised, so recommendations for them stall at the study-material stage.">
            <div className="row wrap">
              {data.concept_performance.length === 0 && Object.keys(data.bank_coverage).length === 0 && (
                <span className="small muted">No questions in the bank.</span>
              )}
              {Object.entries(data.bank_coverage).map(([concept, byDifficulty]) => (
                <span key={concept} className="chip">
                  {concept}: {Object.entries(byDifficulty).map(([d, n]) => `${d[0]}${n}`).join(' ')}
                </span>
              ))}
            </div>
          </Card>
        </div>
      )}
    </Async>
  )
}
