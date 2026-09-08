import { useMemo, useState } from 'react'
import { Card, StatCard } from '../../components/Card.jsx'
import { Async, EmptyState } from '../../components/Loader.jsx'
import { useApi } from '../../hooks/useApi.js'
import { endpoints } from '../../services/api.js'

const DIFFICULTIES = ['Easy', 'Medium', 'Hard']
const TYPES = ['MCQ', 'Numerical', 'Theory']
const DIFFICULTY_CLASS = { Easy: 'badge badge-low', Medium: 'badge badge-med', Hard: 'badge badge-high' }

const BLANK = {
  subject: 'Mathematics', concept: '', difficulty: 'Medium', question_type: 'MCQ',
  question_text: '', correct_answer: '', explanation: '', marks: 1, tolerance: '', source: '',
  options: [{ key: 'A', text: '' }, { key: 'B', text: '' }, { key: 'C', text: '' }, { key: 'D', text: '' }],
}

function QuestionForm({ concepts, editing, onCancel, onSaved }) {
  const [form, setForm] = useState(() => (editing
    ? {
      ...BLANK, ...editing,
      explanation: editing.explanation || '',
      tolerance: editing.tolerance ?? '',
      source: editing.source || '',
      options: editing.options?.length ? editing.options : BLANK.options,
    }
    : { ...BLANK, concept: concepts[0]?.concept || '' }))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [ok, setOk] = useState(null)

  const set = (patch) => setForm((f) => ({ ...f, ...patch }))
  const setOption = (i, text) => set({
    options: form.options.map((o, idx) => (idx === i ? { ...o, text } : o)),
  })

  const submit = async () => {
    setSaving(true); setError(null); setOk(null)
    try {
      const payload = {
        subject: form.subject,
        concept: form.concept,
        difficulty: form.difficulty,
        question_type: form.question_type,
        question_text: form.question_text,
        correct_answer: form.correct_answer,
        explanation: form.explanation || null,
        marks: Number(form.marks) || 1,
        source: form.source || null,
      }
      if (form.question_type === 'MCQ') {
        payload.options = form.options.filter((o) => o.text.trim())
      }
      if (form.question_type === 'Numerical' && form.tolerance !== '') {
        payload.tolerance = Number(form.tolerance)
      }

      if (editing) await endpoints.updateQuestion(editing.question_id, payload)
      else await endpoints.createQuestion(payload)

      setOk(editing ? 'Question updated.' : 'Question created.')
      onSaved()
      if (!editing) setForm({ ...BLANK, concept: form.concept, subject: form.subject })
    } catch (e) { setError(e.message) } finally { setSaving(false) }
  }

  return (
    <Card title={editing ? `Edit question ${editing.question_id}` : 'Add a question'}
      subtitle="Concepts come from the knowledge graph, so every question stays mapped to the curriculum CogniPath reasons over."
      right={editing && <button className="btn btn-sm" onClick={onCancel}>Cancel</button>}>

      <div className="grid grid-4">
        <div className="field">
          <label htmlFor="q-subject">Subject</label>
          <input id="q-subject" value={form.subject} onChange={(e) => set({ subject: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="q-concept">Concept</label>
          <select id="q-concept" value={form.concept} onChange={(e) => set({ concept: e.target.value })}>
            <option value="">Select a concept</option>
            {concepts.map((c) => <option key={c.concept} value={c.concept}>{c.label}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="q-difficulty">Difficulty</label>
          <select id="q-difficulty" value={form.difficulty} onChange={(e) => set({ difficulty: e.target.value })}>
            {DIFFICULTIES.map((d) => <option key={d}>{d}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="q-type">Type</label>
          <select id="q-type" value={form.question_type} onChange={(e) => set({ question_type: e.target.value })}>
            {TYPES.map((t) => <option key={t}>{t}</option>)}
          </select>
        </div>
      </div>

      <div className="field">
        <label htmlFor="q-text">Question</label>
        <textarea id="q-text" rows={3} value={form.question_text}
          onChange={(e) => set({ question_text: e.target.value })} />
      </div>

      {form.question_type === 'MCQ' && (
        <div className="grid grid-2">
          {form.options.map((o, i) => (
            <div className="field" key={o.key}>
              <label htmlFor={`q-opt-${o.key}`}>Option {o.key}</label>
              <input id={`q-opt-${o.key}`} value={o.text} onChange={(e) => setOption(i, e.target.value)} />
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-4">
        <div className="field">
          <label htmlFor="q-answer">
            {form.question_type === 'MCQ' ? 'Correct option key' : 'Correct answer'}
          </label>
          <input id="q-answer" value={form.correct_answer}
            placeholder={form.question_type === 'MCQ' ? 'A' : ''}
            onChange={(e) => set({ correct_answer: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="q-marks">Marks</label>
          <input id="q-marks" type="number" min={1} step="0.5" value={form.marks}
            onChange={(e) => set({ marks: e.target.value })} />
        </div>
        {form.question_type === 'Numerical' && (
          <div className="field">
            <label htmlFor="q-tol">Tolerance</label>
            <input id="q-tol" type="number" step="0.001" value={form.tolerance}
              placeholder="default 1%" onChange={(e) => set({ tolerance: e.target.value })} />
          </div>
        )}
        <div className="field">
          <label htmlFor="q-source">Source</label>
          <input id="q-source" value={form.source} onChange={(e) => set({ source: e.target.value })} />
        </div>
      </div>

      <div className="field">
        <label htmlFor="q-expl">
          {form.question_type === 'Theory' ? 'Model answer shown for self-marking' : 'Explanation'}
        </label>
        <textarea id="q-expl" rows={2} value={form.explanation}
          onChange={(e) => set({ explanation: e.target.value })} />
      </div>

      {error && <div className="notice notice-warn">{error}</div>}
      {ok && <div className="notice">{ok}</div>}

      <button className="btn btn-primary" disabled={saving} onClick={submit}>
        {saving ? 'Saving...' : editing ? 'Save changes' : 'Add question'}
      </button>
    </Card>
  )
}

export default function Questions() {
  const bank = useApi(() => endpoints.bankSummary(), [])
  const [filter, setFilter] = useState({ concept: '', difficulty: '' })
  const [editing, setEditing] = useState(null)
  const [nonce, setNonce] = useState(0)
  const [actionError, setActionError] = useState(null)

  const params = useMemo(() => {
    const p = {}
    if (filter.concept) p.concept = filter.concept
    if (filter.difficulty) p.difficulty = filter.difficulty
    p.limit = 200
    return p
  }, [filter])

  const list = useApi(() => endpoints.questions(params), [params, nonce])

  const refresh = () => { setNonce((n) => n + 1); bank.reload() }

  const retire = async (q) => {
    setActionError(null)
    try {
      await endpoints.deleteQuestion(q.question_id)
      refresh()
    } catch (e) { setActionError(e.message) }
  }

  const concepts = bank.data?.concepts || []

  return (
    <div className="stack">
      <div className="grid grid-4">
        <StatCard label="Active questions" value={bank.data?.total_questions ?? '-'} />
        <StatCard label="Concepts covered"
          value={concepts.filter((c) => c.total > 0).length || '-'}
          hint={`of ${concepts.length} in the curriculum`} />
        <StatCard label="Concepts with no questions"
          value={concepts.filter((c) => !c.total).length || 0}
          hint="Students cannot practise these" />
        <StatCard label="Showing" value={list.data?.count ?? '-'} hint="matching the filter" />
      </div>

      <QuestionForm concepts={concepts} editing={editing}
        onCancel={() => setEditing(null)} onSaved={refresh} />

      <Card title="Question bank"
        right={
          <div className="row">
            <select value={filter.concept} style={{ width: 190 }}
              onChange={(e) => setFilter((f) => ({ ...f, concept: e.target.value }))}>
              <option value="">All concepts</option>
              {concepts.map((c) => <option key={c.concept} value={c.concept}>{c.label}</option>)}
            </select>
            <select value={filter.difficulty} style={{ width: 140 }}
              onChange={(e) => setFilter((f) => ({ ...f, difficulty: e.target.value }))}>
              <option value="">All difficulties</option>
              {DIFFICULTIES.map((d) => <option key={d}>{d}</option>)}
            </select>
          </div>
        }>
        {actionError && <div className="notice notice-warn">{actionError}</div>}
        <Async loading={list.loading} error={list.error} onRetry={list.reload} height={160}
          label="Loading questions...">
          {list.data && (list.data.count ? (
            <div style={{ overflowX: 'auto' }}>
              <table>
                <thead>
                  <tr><th>Question</th><th>Concept</th><th>Difficulty</th><th>Type</th>
                    <th>Marks</th><th>Status</th><th /></tr>
                </thead>
                <tbody>
                  {list.data.questions.map((q) => (
                    <tr key={q.question_id}>
                      <td className="small" style={{ maxWidth: 340 }}>
                        {q.question_text}
                        <div className="tiny muted mono">answer: {q.correct_answer}</div>
                      </td>
                      <td className="small">{q.label || q.concept}</td>
                      <td><span className={DIFFICULTY_CLASS[q.difficulty]}>{q.difficulty}</span></td>
                      <td className="tiny">{q.question_type}</td>
                      <td className="mono">{q.marks}</td>
                      <td>
                        {q.is_active
                          ? <span className="badge badge-low">active</span>
                          : <span className="badge badge-info">retired</span>}
                      </td>
                      <td>
                        <div className="row" style={{ gap: '.3rem' }}>
                          <button className="btn btn-sm" onClick={() => setEditing(q)}>Edit</button>
                          {q.is_active && (
                            <button className="btn btn-sm" onClick={() => retire(q)}>Retire</button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <EmptyState title="No questions match" hint="Adjust the filter or add a question above." />)}
        </Async>
        <p className="tiny muted" style={{ marginTop: '.7rem' }}>
          Retiring a question is a soft delete. Practice attempts reference it, so removing
          the row outright would corrupt historical analytics.
        </p>
      </Card>
    </div>
  )
}
