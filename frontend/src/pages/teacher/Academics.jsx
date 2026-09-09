import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bar as RBar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { Card, StatCard, Bar } from '../../components/Card.jsx'
import { Async, EmptyState } from '../../components/Loader.jsx'
import { useApi } from '../../hooks/useApi.js'
import { endpoints } from '../../services/api.js'
import { percent, riskClass, trendArrow, trendColor } from '../../utils/format.js'

const axis = { stroke: '#9aa6c4', fontSize: 11 }
const tooltip = { background: '#141c33', border: '1px solid #253052', borderRadius: 10, fontSize: 12 }

/** Class-level academic analytics: subject averages, assessment trends and the
 *  early-warning lists (declining, high risk, improving). */
export function SubjectAnalytics() {
  const { data, loading, error, reload } = useApi(() => endpoints.subjectAnalytics(), [])
  const [focus, setFocus] = useState('')

  const assessmentSeries = useMemo(() => {
    if (!data) return []
    const subject = focus || data.subjects[0]?.subject_id
    return data.assessment_trends
      .filter((a) => a.subject_id === subject)
      .sort((a, b) => a.order - b.order)
      .map((a) => ({ name: a.assessment, average: a.average, min: a.min, max: a.max }))
  }, [data, focus])

  return (
    <Async loading={loading} error={error} onRetry={reload} height={140}
      label="Aggregating assessment results across the cohort...">
      {data && (
        data.students_tracked === 0
          ? <EmptyState title="No assessment results recorded"
              hint="Run the academic seed, or record marks from the Assessments page." />
          : (
            <div className="stack">
              <div className="grid grid-4">
                <StatCard label="Students tracked" value={data.students_tracked} />
                <StatCard label="Subjects" value={data.subjects.length} />
                <StatCard label="Declining (subject-level)" value={data.declining_students.length}
                  tone="#f87171" />
                <StatCard label="Improving (subject-level)" value={data.improving_students.length}
                  tone="#34d399" />
              </div>

              <Card title="Subject performance"
                subtitle="Class average of each student's recent assessments, weakest subject first.">
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={data.subjects.map((s) => ({
                    name: s.subject_name, average: s.class_average,
                  }))} layout="vertical" margin={{ left: 10, right: 20 }}>
                    <CartesianGrid stroke="#253052" strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" domain={[0, 100]} {...axis} />
                    <YAxis type="category" dataKey="name" width={170} {...axis} />
                    <Tooltip contentStyle={tooltip} formatter={(v) => [`${v}%`, 'Class average']} />
                    <RBar dataKey="average" barSize={16} radius={[3, 3, 3, 3]}>
                      {data.subjects.map((s, i) => (
                        <Cell key={i} fill={s.class_average < 50 ? '#f87171'
                          : s.class_average < 70 ? '#fbbf24' : '#34d399'} />
                      ))}
                    </RBar>
                  </BarChart>
                </ResponsiveContainer>

                <table style={{ marginTop: '.8rem' }}>
                  <thead>
                    <tr><th>Subject</th><th>Students</th><th>Class average</th>
                      <th>Lowest</th><th>Highest</th><th>Risk split (H/M/L)</th></tr>
                  </thead>
                  <tbody>
                    {data.subjects.map((s) => (
                      <tr key={s.subject_id}>
                        <td className="small">{s.subject_name}</td>
                        <td className="mono">{s.students}</td>
                        <td className="mono">{percent(s.class_average)}</td>
                        <td className="mono">{percent(s.lowest)}</td>
                        <td className="mono">{percent(s.highest)}</td>
                        <td className="mono">
                          {s.risk_distribution.High} / {s.risk_distribution.Medium} / {s.risk_distribution.Low}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>

              <Card title="Assessment trend"
                subtitle="Cohort average per assessment, in chronological order."
                right={
                  <select value={focus} onChange={(e) => setFocus(e.target.value)} style={{ maxWidth: 240 }}>
                    {data.subjects.map((s) => (
                      <option key={s.subject_id} value={s.subject_id}>{s.subject_name}</option>
                    ))}
                  </select>
                }>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={assessmentSeries} margin={{ left: -18, right: 16, top: 8 }}>
                    <CartesianGrid stroke="#253052" strokeDasharray="3 3" />
                    <XAxis dataKey="name" {...axis} />
                    <YAxis domain={[0, 100]} {...axis} />
                    <Tooltip contentStyle={tooltip} />
                    <Line type="monotone" dataKey="average" name="Class average"
                      stroke="#6366f1" strokeWidth={2.4} dot={{ r: 4 }} />
                    <Line type="monotone" dataKey="min" name="Lowest" stroke="#f87171"
                      strokeWidth={1.5} strokeDasharray="4 3" dot={false} />
                    <Line type="monotone" dataKey="max" name="Highest" stroke="#34d399"
                      strokeWidth={1.5} strokeDasharray="4 3" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </Card>

              <div className="grid grid-2">
                <MoverTable title="Early warning: declining students"
                  subtitle="Steepest decline first. A prompt to check in, not a judgement."
                  rows={data.declining_students} />
                <MoverTable title="High-risk subject enrolments"
                  subtitle="Rule-based subject risk, lowest recent average first."
                  rows={data.high_risk_students} />
              </div>

              <MoverTable title="Improving students"
                subtitle="Steepest improvement first - worth acknowledging."
                rows={data.improving_students} />
            </div>
          )
      )}
    </Async>
  )
}

function MoverTable({ title, subtitle, rows }) {
  return (
    <Card title={title} subtitle={subtitle}>
      {rows.length === 0
        ? <p className="small">Nothing in this category right now.</p>
        : (
          <table>
            <thead><tr><th>Student</th><th>Subject</th><th>Recent</th><th>Trend</th><th>Risk</th></tr></thead>
            <tbody>
              {rows.slice(0, 12).map((r) => (
                <tr key={`${r.student_id}-${r.subject_id}`}>
                  <td>
                    <Link to={`/teacher/student/${r.student_id}`} style={{ color: 'var(--brand-2)' }}>
                      {r.display_name || r.student_id}
                    </Link>
                    <div className="tiny muted mono">{r.student_id}</div>
                  </td>
                  <td className="small">{r.subject_name}</td>
                  <td style={{ minWidth: 110 }}>
                    <Bar value={r.recent_average || 0}
                      color={r.recent_average < 50 ? '#f87171' : r.recent_average < 70 ? '#fbbf24' : '#34d399'} />
                    <span className="tiny mono muted">{percent(r.recent_average)}</span>
                  </td>
                  <td>
                    <span style={{ color: trendColor(r.slope > 0 ? 'up' : r.slope < 0 ? 'down' : 'flat') }}
                      aria-hidden>
                      {trendArrow(r.slope > 0 ? 'up' : r.slope < 0 ? 'down' : 'flat')}
                    </span>{' '}
                    <span className="small">{r.trend}</span>
                    <div className="tiny muted">{r.slope > 0 ? '+' : ''}{r.slope} / assessment</div>
                  </td>
                  <td><span className={riskClass(r.risk)}>{r.risk}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
    </Card>
  )
}

/** Subject and assessment management: define assessments and record marks.
 *  Marks entered here flow straight into trends, risk, early warnings and the
 *  assessment-driven prediction. */
export function Assessments() {
  const subjects = useApi(() => endpoints.subjects(), [])
  const [subjectId, setSubjectId] = useState('mathematics')
  const assessments = useApi(() => endpoints.assessments(subjectId), [subjectId])
  const [entry, setEntry] = useState({ assessment_id: '', student_id: '', marks: '' })
  const [status, setStatus] = useState(null)
  const [busy, setBusy] = useState(false)

  const rows = assessments.data?.assessments || []
  const selected = rows.find((a) => String(a.assessment_id) === String(entry.assessment_id))

  const record = async () => {
    setBusy(true); setStatus(null)
    try {
      const result = await endpoints.recordResult(Number(entry.assessment_id), {
        student_id: entry.student_id.trim().toUpperCase(),
        marks: Number(entry.marks),
      })
      setStatus({
        ok: true,
        message: `Recorded ${result.marks} for ${result.student_id} (${result.percentage}%). `
          + 'Trends, risk and the prediction for that student are recalculated from it.',
      })
      setEntry({ ...entry, student_id: '', marks: '' })
    } catch (e) {
      setStatus({ ok: false, message: e.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack">
      <Async loading={subjects.loading} error={subjects.error} onRetry={subjects.reload}
        label="Loading subjects...">
        {subjects.data && (
          <Card title="Subjects"
            subtitle={`${subjects.data.count} subjects. Units and concepts come from the knowledge graph.`}>
            <table>
              <thead><tr><th>Subject</th><th>Code</th><th>Semester</th><th>Units</th><th>Concepts</th><th>Assessments</th></tr></thead>
              <tbody>
                {subjects.data.subjects.map((s) => (
                  <tr key={s.id} onClick={() => setSubjectId(s.id)}>
                    <td className="small">{s.name}</td>
                    <td className="mono tiny">{s.code}</td>
                    <td className="small">{s.semester || '-'}</td>
                    <td className="mono">{s.units.length}</td>
                    <td className="mono">{s.n_concepts}</td>
                    <td className="mono">{s.assessments}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </Async>

      <Async loading={assessments.loading} error={assessments.error} onRetry={assessments.reload}
        label="Loading assessments...">
        {assessments.data && (
          <Card title="Record a mark"
            subtitle="Percentage is derived from the assessment's maximum, so assessments of different sizes stay comparable."
            right={
              <select value={subjectId} onChange={(e) => setSubjectId(e.target.value)} style={{ maxWidth: 240 }}>
                {(subjects.data?.subjects || []).map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            }>
            <div className="grid grid-4">
              <div className="field">
                <label htmlFor="a-assessment">Assessment</label>
                <select id="a-assessment" value={entry.assessment_id}
                  onChange={(e) => setEntry({ ...entry, assessment_id: e.target.value })}>
                  <option value="">Select an assessment</option>
                  {rows.map((a) => (
                    <option key={a.assessment_id} value={a.assessment_id}>
                      {a.name} (max {a.max_marks})
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="a-student">Student ID</label>
                <input id="a-student" placeholder="DEMO004" value={entry.student_id}
                  onChange={(e) => setEntry({ ...entry, student_id: e.target.value })} />
              </div>
              <div className="field">
                <label htmlFor="a-marks">
                  Marks{selected ? ` (0 - ${selected.max_marks})` : ''}
                </label>
                <input id="a-marks" type="number" min="0" step="0.5" value={entry.marks}
                  max={selected?.max_marks}
                  onChange={(e) => setEntry({ ...entry, marks: e.target.value })} />
              </div>
              <div className="field" style={{ display: 'flex', alignItems: 'flex-end' }}>
                <button className="btn btn-primary" onClick={record}
                  disabled={busy || !entry.assessment_id || !entry.student_id || entry.marks === ''}>
                  {busy ? <><span className="spinner" /> Saving...</> : 'Record mark'}
                </button>
              </div>
            </div>

            {status && (
              <div className={status.ok ? 'notice' : 'notice notice-warn'}>{status.message}</div>
            )}

            <table style={{ marginTop: '.8rem' }}>
              <thead><tr><th>#</th><th>Assessment</th><th>Type</th><th>Max marks</th><th>Weight</th></tr></thead>
              <tbody>
                {rows.map((a) => (
                  <tr key={a.assessment_id}>
                    <td className="mono">{a.assessment_order}</td>
                    <td className="small">{a.name}</td>
                    <td className="small">{a.assessment_type}</td>
                    <td className="mono">{a.max_marks}</td>
                    <td className="mono">{a.weight}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </Async>
    </div>
  )
}
