import { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { Card } from '../../components/Card.jsx'
import { endpoints } from '../../services/api.js'
import { STUDY_TIME_LABEL } from '../../utils/format.js'

const NUMERIC = [
  ['G1', 'Period 1 grade (0-20)', 0, 20],
  ['G2', 'Period 2 grade (0-20)', 0, 20],
  ['absences', 'Absences', 0, 93],
  ['failures', 'Past course failures', 0, 4],
  ['health', 'Health status (1-5)', 1, 5],
  ['freetime', 'Free time (1-5)', 1, 5],
  ['goout', 'Going out (1-5)', 1, 5],
  ['age', 'Age', 15, 25],
]

/** Update the student's own academic record and re-run the whole pipeline.
 *  This is the "student enters data -> AI predicts" step of the demo. */
export default function Settings() {
  const { data, reload, studentId } = useOutletContext()
  const f = data.student.features
  const [form, setForm] = useState({
    G1: f.G1, G2: f.G2, absences: f.absences, failures: f.failures, health: f.health,
    freetime: f.freetime, goout: f.goout, age: f.age, studytime: f.studytime,
  })
  const [status, setStatus] = useState(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setStatus(null)
    try {
      await endpoints.createStudent({
        student_id: studentId,
        display_name: data.student.display_name,
        features: Object.fromEntries(Object.entries(form).map(([k, v]) => [k, Number(v)])),
      })
      setStatus({ ok: true, msg: 'Saved. Re-running prediction, explanation and recommendations...' })
      reload()
    } catch (err) {
      setStatus({ ok: false, msg: err.message })
    } finally { setBusy(false) }
  }

  return (
    <Card title="My academic data"
      subtitle="Editing these values re-runs the entire pipeline: prediction, SHAP, root cause, recommendations and study plan.">
      <form onSubmit={submit}>
        <div className="grid grid-3">
          {NUMERIC.map(([key, label, min, max]) => (
            <div className="field" key={key}>
              <label htmlFor={key}>{label}</label>
              <input id={key} type="number" min={min} max={max} step="1" value={form[key]}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })} required />
            </div>
          ))}
          <div className="field">
            <label htmlFor="studytime">Weekly study time</label>
            <select id="studytime" value={form.studytime}
              onChange={(e) => setForm({ ...form, studytime: e.target.value })}>
              {[1, 2, 3, 4].map((v) => <option key={v} value={v}>{STUDY_TIME_LABEL[v]}</option>)}
            </select>
          </div>
        </div>

        {status && (
          <div className={`notice ${status.ok ? '' : 'notice-warn'}`} style={{ margin: '.5rem 0 1rem' }}>
            {status.msg}
          </div>
        )}
        <button className="btn btn-primary" disabled={busy}>{busy ? 'Saving...' : 'Save and re-run analysis'}</button>
      </form>

      <div className="notice" style={{ marginTop: '1.2rem' }}>
        <b>Privacy.</b> The system stores a student ID, a display name and these academic
        indicators only. No contact details or other identifying information are collected.
      </div>
    </Card>
  )
}
