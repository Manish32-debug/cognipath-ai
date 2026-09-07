import { useState } from 'react'
import { Bar, Card } from './Card.jsx'
import { riskClass } from '../utils/format.js'

const color = (m) => (m < 40 ? '#f87171' : m < 60 ? '#fbbf24' : m < 70 ? '#a3a3f5' : '#34d399')

/** Per-concept mastery list. When `onSave` is supplied the values become
 *  editable and are written back as source='self_reported'. */
export default function ConceptMastery({ concepts = [], source, onSave }) {
  const [draft, setDraft] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const editing = draft !== null
  const start = () => setDraft(Object.fromEntries(concepts.map((c) => [c.concept, c.mastery])))

  const save = async () => {
    setSaving(true); setError(null)
    try {
      await onSave(Object.entries(draft).map(([concept, mastery]) => ({
        concept, mastery: Number(mastery), source: 'self_reported',
      })))
      setDraft(null)
    } catch (e) { setError(e.message) } finally { setSaving(false) }
  }

  return (
    <Card title="Concept mastery"
      subtitle={`Target for adequate mastery is 70%. Data source: ${source || 'unknown'}.`}
      right={onSave && (editing
        ? <div className="row">
            <button className="btn btn-sm" onClick={() => setDraft(null)} disabled={saving}>Cancel</button>
            <button className="btn btn-sm btn-primary" onClick={save} disabled={saving}>
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        : <button className="btn btn-sm" onClick={start}>Edit scores</button>)}>

      {source === 'simulated' && (
        <div className="notice notice-warn" style={{ marginBottom: '.9rem' }}>
          These mastery scores are <b>simulated demo data</b>. The source dataset has no
          per-concept assessment scores, so they are generated from this student&apos;s real
          academic record by a documented process. Edit them to use your own values.
        </div>
      )}
      {error && <div className="notice notice-warn" style={{ marginBottom: '.8rem' }}>{error}</div>}

      <div className="stack" style={{ gap: '.7rem' }}>
        {concepts.map((c) => (
          <div key={c.concept}>
            <div className="between" style={{ marginBottom: '.28rem' }}>
              <span className="small">{c.label || c.concept}</span>
              <span className="row" style={{ gap: '.5rem' }}>
                <span className={riskClass(c.risk)}>{c.risk}</span>
                {editing ? (
                  <input type="number" min="0" max="100" step="1"
                    style={{ width: 80, padding: '.2rem .4rem' }}
                    value={draft[c.concept]}
                    onChange={(e) => setDraft({ ...draft, [c.concept]: e.target.value })} />
                ) : <span className="mono small">{Math.round(c.mastery)}%</span>}
              </span>
            </div>
            <Bar value={editing ? Number(draft[c.concept]) : c.mastery} color={color(c.mastery)} />
          </div>
        ))}
      </div>
    </Card>
  )
}
