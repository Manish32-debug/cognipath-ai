import { useEffect, useMemo, useRef, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { Bar, Card, StatCard } from '../../components/Card.jsx'
import { Async, EmptyState } from '../../components/Loader.jsx'
import { useApi } from '../../hooks/useApi.js'
import { endpoints } from '../../services/api.js'
import { minutes, riskClass } from '../../utils/format.js'

const DIFFICULTY_CLASS = { Easy: 'badge badge-low', Medium: 'badge badge-med', Hard: 'badge badge-high' }
const RES_ICON = { Video: '\u25B6', Article: '\u2261', Notes: '\u25A4', PDF: '\u2637', Exercise: '\u2713' }

const clock = (seconds) => {
  const s = Math.max(0, Math.round(seconds || 0))
  return `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s`
}

/** Recommended concepts, each with the reason the engine selected it and a
 *  one-click start. Counts and difficulty come from the backend - nothing here
 *  decides what to practise. */
function RecommendedPractice({ data, onStart, busy }) {
  if (!data?.items?.length) {
    return (
      <EmptyState
        title="Nothing flagged for practice"
        hint={data?.message || 'Every concept is at or above the mastery target.'}
      />
    )
  }

  return (
    <div className="stack">
      {data.items.map((item) => (
        <div key={item.concept} className="card" style={{ background: 'var(--bg-alt)', boxShadow: 'none' }}>
          <div className="between">
            <h3>Priority {item.priority}: {item.label}</h3>
            <span className="row" style={{ gap: '.4rem' }}>
              {item.is_root_cause && <span className="badge badge-root">root cause</span>}
              <span className={riskClass(item.risk)}>{Math.round(item.mastery)}% mastery</span>
            </span>
          </div>

          <Bar value={item.mastery} />

          <p className="small" style={{ margin: '.6rem 0 .4rem' }}>{item.reason}</p>

          {item.resources?.length > 0 && (
            <div className="stack" style={{ gap: '.3rem', margin: '.6rem 0' }}>
              <div className="tiny muted">Study this first</div>
              {item.resources.map((r) => (
                <a key={r.resource_id} href={r.url} target="_blank" rel="noreferrer"
                  className="between small"
                  style={{ padding: '.4rem .55rem', border: '1px solid var(--border)', borderRadius: 8 }}>
                  <span>
                    <span aria-hidden style={{ color: 'var(--brand-2)' }}>{RES_ICON[r.resource_type] || '\u2022'}</span>
                    {' '}{r.title}
                  </span>
                  <span className="tiny muted">{r.resource_type} &middot; {minutes(r.estimated_minutes)}</span>
                </a>
              ))}
            </div>
          )}

          <div className="between" style={{ marginTop: '.7rem' }}>
            <span className="row" style={{ gap: '.4rem' }}>
              <span className={DIFFICULTY_CLASS[item.difficulty]}>{item.difficulty}</span>
              <span className="tiny muted">
                {item.available_questions} of {item.recommended_questions} recommended questions available
                {item.downstream_concepts > 0 && ` \u00B7 unlocks ${item.downstream_concepts} concept(s)`}
              </span>
            </span>
            <button className="btn btn-primary btn-sm" disabled={busy || !item.available_questions}
              onClick={() => onStart({
                concept: item.concept,
                difficulty: item.difficulty,
                count: item.available_questions,
                origin: item.is_root_cause ? 'root_cause' : 'recommended',
              })}>
              {item.available_questions ? `Practice ${item.available_questions} questions` : 'No questions yet'}
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

function QuestionRunner({ session, answers, setAnswers, onSubmit, submitting, error }) {
  const [index, setIndex] = useState(0)
  const question = session.questions[index]
  const answered = Object.keys(answers).length
  const current = answers[question.question_id]

  const setAnswer = (value, extra = {}) =>
    setAnswers((prev) => ({ ...prev, [question.question_id]: { value, ...extra } }))

  return (
    <Card
      title={`Question ${index + 1} of ${session.questions.length}`}
      subtitle={`${session.label} \u00B7 ${question.question_type} \u00B7 ${question.marks} mark${question.marks === 1 ? '' : 's'}`}
      right={<span className={DIFFICULTY_CLASS[question.difficulty]}>{question.difficulty}</span>}>

      <Bar value={(100 * answered) / session.questions.length} color="var(--brand-2)" />

      <p style={{ margin: '1rem 0', fontSize: '1.05rem' }}>{question.question_text}</p>

      {question.question_type === 'MCQ' && (
        <div className="stack" style={{ gap: '.4rem' }}>
          {question.options.map((opt) => {
            const selected = current?.value === opt.key
            return (
              <button key={opt.key} className="btn"
                style={{
                  justifyContent: 'flex-start', textAlign: 'left',
                  borderColor: selected ? 'var(--brand)' : 'var(--border)',
                  background: selected ? 'var(--surface-2)' : undefined,
                }}
                onClick={() => setAnswer(opt.key)}>
                <b className="mono" style={{ marginRight: '.6rem' }}>{opt.key}.</b> {opt.text}
              </button>
            )
          })}
        </div>
      )}

      {question.question_type === 'Numerical' && (
        <div className="field">
          <label htmlFor="numeric-answer">Your answer</label>
          <input id="numeric-answer" inputMode="decimal" placeholder="e.g. 3.162"
            value={current?.value || ''} onChange={(e) => setAnswer(e.target.value)} />
          <div className="tiny muted">Fractions such as 3/4 are accepted.</div>
        </div>
      )}

      {question.question_type === 'Theory' && (
        <div className="stack">
          <div className="field">
            <label htmlFor="theory-answer">Your answer</label>
            <textarea id="theory-answer" rows={5} value={current?.value || ''}
              onChange={(e) => setAnswer(e.target.value, { self: current?.self })} />
          </div>
          <div className="notice">
            Theory answers are self-marked. You will compare yours against the model
            answer at the end and mark it yourself; self-marked answers are excluded
            from the learning-state update.
          </div>
          <div className="row">
            <button className={`btn btn-sm ${current?.self === true ? 'btn-primary' : ''}`}
              onClick={() => setAnswer(current?.value || '', { self: true })}>
              I got this right
            </button>
            <button className={`btn btn-sm ${current?.self === false ? 'btn-primary' : ''}`}
              onClick={() => setAnswer(current?.value || '', { self: false })}>
              I got this wrong
            </button>
          </div>
        </div>
      )}

      {error && <div className="notice notice-warn" style={{ marginTop: '.8rem' }}>{error}</div>}

      <div className="between" style={{ marginTop: '1.2rem' }}>
        <button className="btn btn-sm" disabled={index === 0} onClick={() => setIndex((i) => i - 1)}>
          Previous
        </button>
        <span className="tiny muted">{answered} of {session.questions.length} answered</span>
        {index < session.questions.length - 1 ? (
          <button className="btn btn-primary btn-sm" onClick={() => setIndex((i) => i + 1)}>Next</button>
        ) : (
          <button className="btn btn-primary btn-sm" disabled={submitting || !answered} onClick={onSubmit}>
            {submitting ? 'Submitting...' : 'Submit answers'}
          </button>
        )}
      </div>
    </Card>
  )
}

function Results({ result, onDone }) {
  const s = result.summary
  const changes = result.mastery_update?.changes || []

  return (
    <div className="stack">
      <div className="grid grid-4">
        <StatCard label="Score" value={s.score} suffix={`/ ${s.max_score}`} />
        <StatCard label="Accuracy" value={s.accuracy} suffix="%"
          tone={s.accuracy >= 70 ? 'var(--good)' : s.accuracy >= 50 ? 'var(--warn)' : 'var(--bad)'} />
        <StatCard label="Correct" value={`${s.correct} / ${s.total_questions}`}
          hint={`${s.incorrect} incorrect`} />
        <StatCard label="Time taken" value={clock(s.time_taken_seconds)} />
      </div>

      {changes.length > 0 && (
        <Card title="Learning state updated"
          subtitle={result.mastery_update.config.formula}>
          <div className="stack" style={{ gap: '.5rem' }}>
            {changes.map((c) => (
              <div key={c.concept} className="between small"
                style={{ padding: '.5rem .6rem', border: '1px solid var(--border)', borderRadius: 8 }}>
                <span>{c.concept}</span>
                <span className="mono">
                  {c.previous}% &rarr;{' '}
                  <b style={{ color: c.delta >= 0 ? 'var(--good)' : 'var(--bad)' }}>{c.updated}%</b>
                  <span className="tiny muted">
                    {' '}({c.delta >= 0 ? '+' : ''}{c.delta}, alpha {c.alpha_effective}, n={c.graded_attempts})
                  </span>
                </span>
              </div>
            ))}
          </div>
          <p className="tiny muted" style={{ marginTop: '.7rem' }}>{result.mastery_update.note}</p>
        </Card>
      )}

      {result.root_cause?.current?.length > 0 && (
        <Card title="Root-cause diagnosis after this session"
          subtitle={result.root_cause.changed
            ? 'The prerequisite analysis re-ran on your updated mastery and the ordering changed.'
            : 'The prerequisite analysis re-ran on your updated mastery; the ordering is unchanged.'}>
          <div className="row wrap">
            {result.root_cause.current.map((r) => (
              <span key={r.concept} className="badge badge-root">
                {r.label} &middot; {Math.round(r.mastery)}%
              </span>
            ))}
          </div>
        </Card>
      )}

      <Card title="Concept performance">
        <table>
          <thead><tr><th>Concept</th><th>Attempted</th><th>Correct</th><th>Accuracy</th></tr></thead>
          <tbody>
            {s.concept_performance.map((c) => (
              <tr key={c.concept}>
                <td>{c.concept}</td>
                <td className="mono">{c.attempted}</td>
                <td className="mono">{c.correct}</td>
                <td className="mono">{c.accuracy}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card title="Answer review">
        <div className="stack">
          {result.results.map((r, i) => (
            <div key={r.question_id} className="card"
              style={{
                background: 'var(--bg-alt)', boxShadow: 'none',
                borderColor: r.is_correct ? 'rgba(52,211,153,.4)' : 'rgba(248,113,113,.4)',
              }}>
              <div className="between">
                <b className="small">Q{i + 1}. {r.question_text}</b>
                <span className={r.is_correct ? 'badge badge-low' : 'badge badge-high'}>
                  {r.is_correct ? 'correct' : 'incorrect'} &middot; {r.score}/{r.max_score}
                </span>
              </div>
              <p className="small" style={{ margin: '.5rem 0 .2rem' }}>
                Your answer: <span className="mono">{r.your_answer || '(blank)'}</span>
              </p>
              <p className="small" style={{ margin: '0 0 .4rem' }}>
                Correct answer: <span className="mono">{r.correct_answer}</span>
                {r.graded_by === 'self' && <span className="tiny muted"> (self-marked)</span>}
              </p>
              {r.explanation && <p className="small muted" style={{ margin: 0 }}>{r.explanation}</p>}
            </div>
          ))}
        </div>
      </Card>

      <button className="btn btn-primary" onClick={onDone}>Practise something else</button>
    </div>
  )
}

export default function Practice() {
  const { studentId, reload: reloadDashboard } = useOutletContext()
  const { data: recommended, error, loading, reload } = useApi(
    () => endpoints.recommendedPractice(studentId), [studentId], { enabled: Boolean(studentId) },
  )
  const { data: bank } = useApi(() => endpoints.bankSummary(), [])

  const [session, setSession] = useState(null)
  const [answers, setAnswers] = useState({})
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState(null)
  const startedAt = useRef(null)

  // Manual selection
  const [concept, setConcept] = useState('')
  const [difficulty, setDifficulty] = useState('')
  const [count, setCount] = useState(5)

  const conceptsWithQuestions = useMemo(
    () => (bank?.concepts || []).filter((c) => c.total > 0), [bank],
  )

  useEffect(() => {
    if (!concept && conceptsWithQuestions.length) setConcept(conceptsWithQuestions[0].concept)
  }, [conceptsWithQuestions, concept])

  const start = async (payload) => {
    setBusy(true); setFormError(null); setResult(null)
    try {
      const s = await endpoints.startPractice(studentId, payload)
      startedAt.current = Date.now()
      setAnswers({})
      setSession(s)
    } catch (e) { setFormError(e.message) } finally { setBusy(false) }
  }

  const submit = async () => {
    setBusy(true); setFormError(null)
    try {
      const payload = {
        session_id: session.session_id,
        elapsed_seconds: (Date.now() - startedAt.current) / 1000,
        answers: session.questions
          .filter((q) => answers[q.question_id])
          .map((q) => ({
            question_id: q.question_id,
            selected_answer: answers[q.question_id].value ?? null,
            self_marked_correct: q.question_type === 'Theory'
              ? Boolean(answers[q.question_id].self) : undefined,
          })),
      }
      const r = await endpoints.submitPractice(payload)
      setResult(r)
      setSession(null)
      reload()
      reloadDashboard()
    } catch (e) { setFormError(e.message) } finally { setBusy(false) }
  }

  if (result) {
    return <Results result={result} onDone={() => setResult(null)} />
  }

  if (session) {
    return (
      <QuestionRunner session={session} answers={answers} setAnswers={setAnswers}
        onSubmit={submit} submitting={busy} error={formError} />
    )
  }

  return (
    <div className="stack">
      <Card title="Recommended practice"
        subtitle="Concepts ranked by the same priority score that drives your recommendations: root-cause evidence, mastery gap, downstream impact and predicted risk.">
        {formError && <div className="notice notice-warn" style={{ marginBottom: '.8rem' }}>{formError}</div>}
        <Async loading={loading} error={error} onRetry={reload} height={160}
          label="Ranking concepts and checking the question bank...">
          {recommended && <RecommendedPractice data={recommended} onStart={start} busy={busy} />}
        </Async>
      </Card>

      <Card title="Free practice" subtitle="Pick any concept in the question bank.">
        <div className="grid grid-4">
          <div className="field">
            <label htmlFor="pc-concept">Concept</label>
            <select id="pc-concept" value={concept} onChange={(e) => setConcept(e.target.value)}>
              {conceptsWithQuestions.map((c) => (
                <option key={c.concept} value={c.concept}>{c.label} ({c.total})</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="pc-difficulty">Difficulty</label>
            <select id="pc-difficulty" value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
              <option value="">Any</option>
              {['Easy', 'Medium', 'Hard'].map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="pc-count">Questions</label>
            <input id="pc-count" type="number" min={1} max={25} value={count}
              onChange={(e) => setCount(Number(e.target.value))} />
          </div>
          <div className="field" style={{ justifyContent: 'flex-end' }}>
            <button className="btn btn-primary" disabled={busy || !concept}
              onClick={() => start({ concept, difficulty: difficulty || undefined, count, origin: 'manual' })}>
              {busy ? 'Starting...' : 'Start practice'}
            </button>
          </div>
        </div>
        {!conceptsWithQuestions.length && (
          <p className="small muted">The question bank is empty. Ask a teacher to add questions.</p>
        )}
      </Card>
    </div>
  )
}
