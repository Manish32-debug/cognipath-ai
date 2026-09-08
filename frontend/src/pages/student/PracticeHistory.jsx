import { useOutletContext } from 'react-router-dom'
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Bar, Card, StatCard } from '../../components/Card.jsx'
import { Async, EmptyState } from '../../components/Loader.jsx'
import { useApi } from '../../hooks/useApi.js'
import { endpoints } from '../../services/api.js'

const accuracyColor = (a) => (a >= 70 ? 'var(--good)' : a >= 50 ? 'var(--warn)' : 'var(--bad)')
const clock = (s) => (s == null ? '-' : `${Math.floor(s / 60)}m ${String(Math.round(s % 60)).padStart(2, '0')}s`)

function MasteryTrajectory({ history }) {
  if (!history?.length) return null

  // One line per concept, oldest first.
  const ordered = [...history].reverse()
  const concepts = [...new Set(ordered.map((h) => h.concept))]
  const series = ordered.map((h, i) => ({
    step: i + 1,
    concept: h.concept,
    mastery: h.updated,
    previous: h.previous,
  }))

  return (
    <Card title="Learning-state trajectory"
      subtitle="Each point is one practice session's effect on concept mastery. Mastery here is an application-maintained estimate, not a validated assessment score.">
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={series}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="step" stroke="var(--muted)" fontSize={12} />
          <YAxis domain={[0, 100]} stroke="var(--muted)" fontSize={12} />
          <Tooltip
            contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
            formatter={(value, _name, item) => [`${value}%`, item.payload.concept]} />
          <Line type="monotone" dataKey="mastery" stroke="var(--brand-2)" strokeWidth={2} dot />
        </LineChart>
      </ResponsiveContainer>
      <div className="tiny muted">Concepts in this trajectory: {concepts.join(', ')}</div>
    </Card>
  )
}

export default function PracticeHistory() {
  const { studentId } = useOutletContext()
  const perf = useApi(() => endpoints.practicePerformance(studentId), [studentId],
    { enabled: Boolean(studentId) })
  const hist = useApi(() => endpoints.practiceHistory(studentId), [studentId],
    { enabled: Boolean(studentId) })

  return (
    <div className="stack">
      <Async loading={perf.loading} error={perf.error} onRetry={perf.reload} height={140}
        label="Aggregating your practice attempts...">
        {perf.data && (
          <>
            <div className="grid grid-4">
              <StatCard label="Questions attempted" value={perf.data.totals.attempted} />
              <StatCard label="Correct" value={perf.data.totals.correct}
                hint={`${perf.data.totals.incorrect} incorrect`} />
              <StatCard label="Overall accuracy" value={perf.data.totals.accuracy} suffix="%"
                tone={accuracyColor(perf.data.totals.accuracy)} />
              <StatCard label="Total score" value={perf.data.totals.score}
                suffix={`/ ${perf.data.totals.max_score}`} />
            </div>

            {perf.data.concepts.length ? (
              <Card title="Concept performance"
                subtitle="Computed from every stored attempt, alongside your current learning state.">
                <div style={{ overflowX: 'auto' }}>
                  <table>
                    <thead>
                      <tr>
                        <th>Concept</th><th>Attempted</th><th>Correct</th>
                        <th>Accuracy</th><th>Current mastery</th><th>Avg. time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {perf.data.concepts.map((c) => (
                        <tr key={c.concept}>
                          <td>{c.label || c.concept}</td>
                          <td className="mono">{c.attempted}</td>
                          <td className="mono">{c.correct}</td>
                          <td className="mono" style={{ color: accuracyColor(c.accuracy) }}>{c.accuracy}%</td>
                          <td style={{ minWidth: 120 }}>
                            {c.current_mastery != null ? (
                              <>
                                <span className="mono tiny">{Math.round(c.current_mastery)}%</span>
                                <Bar value={c.current_mastery} />
                              </>
                            ) : <span className="tiny muted">-</span>}
                          </td>
                          <td className="mono tiny">{c.avg_time_seconds ? `${c.avg_time_seconds}s` : '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            ) : (
              <EmptyState title="No practice attempts yet"
                hint="Answer some questions on the Practice page and your concept statistics will appear here." />
            )}

            <MasteryTrajectory history={perf.data.mastery_history} />
          </>
        )}
      </Async>

      <Card title="Session history" subtitle="Your most recent completed practice sessions.">
        <Async loading={hist.loading} error={hist.error} onRetry={hist.reload} height={120}
          label="Loading sessions...">
          {hist.data && (hist.data.sessions.length ? (
            <div style={{ overflowX: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th>When</th><th>Concept</th><th>Difficulty</th><th>Origin</th>
                    <th>Questions</th><th>Accuracy</th><th>Score</th><th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {hist.data.sessions.map((s) => (
                    <tr key={s.session_id}>
                      <td className="tiny">{s.completed_at}</td>
                      <td>{s.label || s.concept || '-'}</td>
                      <td className="tiny">{s.difficulty || 'Any'}</td>
                      <td><span className="chip">{s.origin.replace('_', ' ')}</span></td>
                      <td className="mono">{s.questions}</td>
                      <td className="mono" style={{ color: accuracyColor(s.accuracy) }}>{s.accuracy}%</td>
                      <td className="mono">{s.score}/{s.max_score}</td>
                      <td className="mono tiny">{clock(s.time_taken)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <EmptyState title="No sessions yet" hint="Completed practice sessions appear here." />)}
        </Async>
      </Card>
    </div>
  )
}
