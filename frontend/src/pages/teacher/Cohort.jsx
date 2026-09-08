import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Async } from '../../components/Loader.jsx'
import { Card, StatCard } from '../../components/Card.jsx'
import { ConceptWeaknessChart, RiskDistributionChart } from '../../charts/CohortCharts.jsx'
import { useApi } from '../../hooks/useApi.js'
import { endpoints } from '../../services/api.js'
import { num, riskClass, riskColor } from '../../utils/format.js'

/** Cohort overview - the original teacher dashboard body, unchanged, now an
 *  index route inside the teacher layout. */
export default function Cohort() {
  const { data, error, loading, reload } = useApi(() => endpoints.analytics(), [])
  const [query, setQuery] = useState('')
  const [risk, setRisk] = useState('All')
  const navigate = useNavigate()

  const rows = useMemo(() => {
    const all = data?.students || []
    return all.filter((s) => {
      const matches = `${s.student_id} ${s.display_name || ''}`.toLowerCase().includes(query.toLowerCase())
      return matches && (risk === 'All' || s.risk_tier === risk)
    })
  }, [data, query, risk])

  return (
    <Async loading={loading} error={error} onRetry={reload} height={140}
      label="Scoring the cohort with the trained models...">
      {data && (
        <div className="stack">
          <div className="grid grid-4">
            <StatCard label="Students" value={data.total_students} />
            <StatCard label="Average predicted GPA" value={num(data.average_predicted_gpa)} suffix="/ 10" />
            <StatCard label="Average attendance" value={num(data.average_attendance, 1)} suffix="%" />
            <StatCard label="High risk" value={data.risk_distribution.High || 0}
              tone={riskColor('High')} hint="Flagged for intervention" />
          </div>

          <div className="grid grid-2">
            <Card title="Risk distribution" subtitle="Predicted by the risk-tier classifier.">
              <RiskDistributionChart distribution={data.risk_distribution} />
            </Card>
            <Card title="Weakest concepts across the cohort"
              subtitle="Average mastery per concept; the lowest ten are shown.">
              <ConceptWeaknessChart concepts={data.concept_summary} />
            </Card>
          </div>

          <Card title="Students requiring intervention"
            subtitle="Predicted high risk, ordered by lowest predicted GPA."
            right={<span className="chip">{data.students_requiring_intervention.length} flagged</span>}>
            <div className="row wrap">
              {data.students_requiring_intervention.map((s) => (
                <button key={s.student_id} className="btn btn-sm"
                  onClick={() => navigate(`/teacher/student/${s.student_id}`)}>
                  {s.display_name} &middot; GPA {num(s.predicted_gpa)}
                  {s.top_root_cause ? ` \u00B7 ${s.top_root_cause}` : ''}
                </button>
              ))}
              {!data.students_requiring_intervention.length && <span className="small muted">None flagged.</span>}
            </div>
          </Card>

          <Card title="Cohort" subtitle="Search, filter by risk, then open a student for the full explanation."
            right={
              <div className="row">
                <input placeholder="Search name or ID" value={query} style={{ width: 200 }}
                  onChange={(e) => setQuery(e.target.value)} />
                <select value={risk} onChange={(e) => setRisk(e.target.value)} style={{ width: 150 }}>
                  {['All', 'High', 'Medium', 'Low'].map((r) => <option key={r}>{r}</option>)}
                </select>
              </div>
            }>
            <div style={{ overflowX: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th>Student</th><th>Predicted GPA</th><th>Pass prob.</th><th>Risk</th>
                    <th>Attendance</th><th>Mastery</th><th>Weak</th><th>Likely root cause</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((s) => (
                    <tr key={s.student_id} onClick={() => navigate(`/teacher/student/${s.student_id}`)}>
                      <td>{s.display_name}<div className="tiny muted mono">{s.student_id}</div></td>
                      <td className="mono">{num(s.predicted_gpa)}</td>
                      <td className="mono">{num(s.pass_probability * 100, 0)}%</td>
                      <td><span className={riskClass(s.risk_tier)}>{s.risk_tier}</span></td>
                      <td className="mono">{num(s.attendance_pct, 0)}%</td>
                      <td className="mono">{num(s.overall_mastery, 0)}%</td>
                      <td className="mono">{s.weak_concepts}</td>
                      <td className="small">{s.top_root_cause || '-'}</td>
                    </tr>
                  ))}
                  {!rows.length && <tr><td colSpan={8} className="small muted">No students match this filter.</td></tr>}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </Async>
  )
}
