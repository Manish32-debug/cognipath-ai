import { Link, useOutletContext, useParams } from 'react-router-dom'
import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Card, StatCard, Bar } from '../../components/Card.jsx'
import { Async, EmptyState } from '../../components/Loader.jsx'
import KnowledgeGraph from '../../graph/KnowledgeGraph.jsx'
import { useApi } from '../../hooks/useApi.js'
import { endpoints } from '../../services/api.js'
import {
  num, percent, riskClass, riskColor, trendArrow, trendColor,
} from '../../utils/format.js'

/** One subject, end to end: assessment timeline, trend, risk, concept mastery,
 *  subject knowledge graph, root causes, recommended practice and context advice.
 *  Every panel renders a value the API computed. */
export default function SubjectDetail() {
  const { studentId } = useOutletContext()
  const { subjectId } = useParams()
  const detail = useApi(() => endpoints.subjectDetail(studentId, subjectId),
    [studentId, subjectId], { enabled: Boolean(studentId && subjectId) })
  const graph = useApi(() => endpoints.subjectGraph(subjectId), [subjectId],
    { enabled: Boolean(subjectId) })

  return (
    <div className="stack">
      <div className="between">
        <Link to="/app/academics" className="btn btn-sm btn-ghost">
          <span aria-hidden>&larr;</span> All subjects
        </Link>
      </div>

      <Async loading={detail.loading} error={detail.error} onRetry={detail.reload}
        height={150} label="Loading assessment history, mastery and root causes...">
        {detail.data && (
          detail.data.performance === null
            ? <EmptyState title="No results for this subject yet"
                hint="Assessment marks appear here once a teacher records them." />
            : <SubjectBody detail={detail.data} graph={graph} subjectId={subjectId} />
        )}
      </Async>
    </div>
  )
}

function SubjectBody({ detail, graph, subjectId }) {
  const { performance, mastery, root_causes: roots, practice_plan: plan,
    context_advice: advice, ml_prediction: ml, practice_performance: practice } = detail
  const { summary, trend, risk, assessments } = performance

  const series = assessments.map((a) => ({
    name: a.name, percentage: a.percentage, marks: a.marks, max: a.max_marks, source: a.source,
  }))
  const masteryMap = {}
  mastery.concepts.forEach((c) => { masteryMap[c.concept] = c.mastery })

  return (
    <>
      <div className="grid grid-4">
        <StatCard label="Current level" value={percent(summary.recent_average)}
          hint={`Latest assessment ${percent(summary.current)}`} />
        <StatCard label="Subject average" value={percent(summary.average)}
          hint={`Best ${percent(summary.best)} \u00B7 worst ${percent(summary.worst)}`} />
        <StatCard label="Trend" value={`${trendArrow(trend.direction)} ${trend.trend}`}
          tone={trendColor(trend.direction)}
          hint={`${trend.slope > 0 ? '+' : ''}${trend.slope} points per assessment`} />
        <StatCard label="Subject risk" value={risk.risk} tone={riskColor(risk.risk)}
          hint={`Consistency ${percent(summary.consistency)}`} />
      </div>

      <Card title={`${performance.subject_name} \u2014 assessment timeline`}
        subtitle={`${summary.n_assessments} recorded assessments. ${trend.description}`}>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={series} margin={{ left: -18, right: 16, top: 8 }}>
            <CartesianGrid stroke="#253052" strokeDasharray="3 3" />
            <XAxis dataKey="name" stroke="#9aa6c4" fontSize={11} />
            <YAxis domain={[0, 100]} stroke="#9aa6c4" fontSize={11} />
            <ReferenceLine y={40} stroke="#f87171" strokeDasharray="4 3"
              label={{ value: 'pass mark', fill: '#f87171', fontSize: 10, position: 'insideBottomRight' }} />
            <Tooltip
              contentStyle={{ background: '#141c33', border: '1px solid #253052', borderRadius: 10, fontSize: 12 }}
              formatter={(value, _n, p) => [`${value}% (${p.payload.marks}/${p.payload.max})`, 'Score']} />
            <Line type="monotone" dataKey="percentage" stroke="#6366f1" strokeWidth={2.4}
              dot={{ r: 4, fill: '#22d3ee' }} activeDot={{ r: 6 }} />
          </LineChart>
        </ResponsiveContainer>

        <div className="notice" style={{ marginTop: '.6rem' }}>
          <b>Risk reasoning:</b> {risk.reason} <span className="tiny">({risk.method})</span>
        </div>

        <table style={{ marginTop: '.8rem' }}>
          <thead><tr><th>Assessment</th><th>Type</th><th>Marks</th><th>Percentage</th><th>Source</th></tr></thead>
          <tbody>
            {assessments.map((a) => (
              <tr key={a.assessment_id}>
                <td className="small">{a.name}</td>
                <td className="small">{a.type}</td>
                <td className="mono">{a.marks} / {a.max_marks}</td>
                <td className="mono">{percent(a.percentage)}</td>
                <td className="tiny muted">{a.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {ml?.prediction && (
        <Card title="Model prediction for this subject" subtitle={ml.basis}>
          <div className="grid grid-3">
            <StatCard label="Predicted GPA" value={num(ml.prediction.predicted_gpa)} suffix="/ 10" />
            <StatCard label="Pass probability" value={percent(ml.prediction.pass_probability * 100)} />
            <StatCard label="Risk tier" value={ml.prediction.risk_tier}
              tone={riskColor(ml.prediction.risk_tier)} />
          </div>
        </Card>
      )}

      <div className="grid grid-2">
        <Card title="Concept mastery in this subject"
          subtitle={`Source: ${mastery.source}. Subject average ${percent(mastery.average)}.`}>
          {mastery.concepts.length === 0
            ? <p className="small">No concept mastery recorded for this subject yet.</p>
            : (
              <div className="stack" style={{ gap: '.7rem' }}>
                {mastery.concepts.map((c) => (
                  <div key={c.concept}>
                    <div className="between" style={{ marginBottom: '.2rem' }}>
                      <span className="small">{c.label} <span className="tiny muted">({c.unit})</span></span>
                      <span className="row">
                        <span className={riskClass(c.risk)}>{c.risk}</span>
                        <span className="tiny mono muted">{percent(c.mastery)}</span>
                      </span>
                    </div>
                    <Bar value={c.mastery}
                      color={c.mastery < 40 ? '#f87171' : c.mastery < 60 ? '#fbbf24' : '#34d399'} />
                  </div>
                ))}
              </div>
            )}
        </Card>

        <Card title="Likely root causes"
          subtitle="Traced through prerequisites, which may sit in another subject.">
          {roots.length === 0
            ? <p className="small">No concept in this subject is below the mastery target.</p>
            : (
              <div className="stack">
                {roots.map((r) => (
                  <div key={r.concept} className="card"
                    style={{ background: 'var(--bg-alt)', boxShadow: 'none' }}>
                    <div className="row wrap">
                      <span className="badge badge-root">likely root cause</span>
                      <strong>{r.label}</strong>
                      <span className={riskClass(r.risk)}>{percent(r.mastery)}</span>
                    </div>
                    <p className="small" style={{ margin: '.5rem 0 0' }}>{r.reasoning}</p>
                    {r.affected_concepts?.length > 0 && (
                      <div className="tiny mono muted" style={{ marginTop: '.4rem' }}>
                        {r.affected_concepts[0].path_labels.join('  \u2192  ')}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
        </Card>
      </div>

      <Async loading={graph.loading} error={graph.error} onRetry={graph.reload}
        label="Loading the subject knowledge graph..." height={260}>
        {graph.data && (
          <Card title={`${graph.data.subject_name} prerequisite graph`}
            subtitle={`${graph.data.stats.n_nodes} concepts, ${graph.data.stats.n_edges} prerequisites. Node values are your mastery.`}>
            <KnowledgeGraph graph={graph.data} mastery={masteryMap} rootCauses={roots} />
            {graph.data.external_prerequisites?.length > 0 && (
              <div className="tiny muted" style={{ marginTop: '.6rem' }}>
                Prerequisites from other subjects:{' '}
                {graph.data.external_prerequisites
                  .map((e) => `${e.source_label} \u2192 ${e.target_label}`)
                  .join(', ')}
              </div>
            )}
          </Card>
        )}
      </Async>

      <Card title="Recommended practice for this subject"
        subtitle={plan.message || 'Difficulty is matched to your current mastery in each concept.'}
        right={practice.attempted
          ? <span className="chip">{practice.attempted} attempts \u00B7 {percent((practice.accuracy || 0) * 100)} accuracy</span>
          : undefined}>
        {plan.items.length === 0
          ? <p className="small">Nothing below the mastery target in this subject.</p>
          : (
            <div className="stack">
              {plan.items.map((item) => (
                <div key={item.concept} className="card"
                  style={{ background: 'var(--bg-alt)', boxShadow: 'none' }}>
                  <div className="between">
                    <div className="row wrap">
                      <strong>{item.label}</strong>
                      <span className={riskClass(item.risk)}>{percent(item.mastery)} mastery</span>
                      <span className="chip">{item.difficulty}</span>
                      {item.is_root_cause && <span className="badge badge-root">root cause</span>}
                    </div>
                    <Link to="/app/practice" className="btn btn-sm btn-primary">
                      Practice {item.available_questions || item.recommended_questions} questions
                    </Link>
                  </div>
                  <p className="small" style={{ margin: '.5rem 0 0' }}>{item.reason}</p>
                  {item.resources?.length > 0 && (
                    <div className="tiny muted" style={{ marginTop: '.4rem' }}>
                      Study first: {item.resources.map((r) => r.title).join(' \u00B7 ')}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
      </Card>

      <Card title="How to study this subject"
        subtitle="Rule-based advice from your attendance, study time, trend, mastery and practice accuracy.">
        <div className="stack">
          {advice.map((a, i) => (
            <div key={i} className="card" style={{ background: 'var(--bg-alt)', boxShadow: 'none' }}>
              <div className="row wrap">
                <strong>{a.strategy}</strong>
                <span className="chip tiny">rule: {a.rule}</span>
              </div>
              <p className="small" style={{ margin: '.45rem 0 .3rem' }}>{a.advice}</p>
              <div className="tiny muted">{a.why}</div>
              <ul className="small" style={{ margin: '.4rem 0 0 1rem', color: 'var(--muted)' }}>
                {a.actions.map((action, k) => <li key={k}>{action}</li>)}
              </ul>
            </div>
          ))}
        </div>
      </Card>
    </>
  )
}
