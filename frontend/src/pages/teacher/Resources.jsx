import { useState } from 'react'
import { Card, StatCard } from '../../components/Card.jsx'
import { Async, EmptyState } from '../../components/Loader.jsx'
import { useApi } from '../../hooks/useApi.js'
import { endpoints } from '../../services/api.js'
import { minutes } from '../../utils/format.js'

const TYPES = ['Video', 'Article', 'Notes', 'PDF', 'Exercise']
const DIFFICULTIES = ['Easy', 'Medium', 'Hard']
const BLANK = {
  title: '', subject: 'Mathematics', concept: '', resource_type: 'Notes',
  difficulty: 'Medium', description: '', url: '', estimated_minutes: 20,
}

export default function TeacherResources() {
  const bank = useApi(() => endpoints.bankSummary(), [])
  const [nonce, setNonce] = useState(0)
  const list = useApi(() => endpoints.resources(), [nonce])

  const [form, setForm] = useState(BLANK)
  const [editingId, setEditingId] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [ok, setOk] = useState(null)

  const set = (patch) => setForm((f) => ({ ...f, ...patch }))
  const refresh = () => setNonce((n) => n + 1)

  const submit = async () => {
    setSaving(true); setError(null); setOk(null)
    try {
      const payload = {
        ...form,
        description: form.description || null,
        url: form.url || null,
        estimated_minutes: Number(form.estimated_minutes) || 20,
      }
      if (editingId) await endpoints.updateResource(editingId, payload)
      else await endpoints.createResource(payload)
      setOk(editingId ? 'Resource updated.' : 'Resource added.')
      setForm({ ...BLANK, concept: form.concept, subject: form.subject })
      setEditingId(null)
      refresh()
    } catch (e) { setError(e.message) } finally { setSaving(false) }
  }

  const edit = (r) => {
    setEditingId(r.resource_id)
    setForm({
      title: r.title, subject: r.subject, concept: r.concept,
      resource_type: r.resource_type, difficulty: r.difficulty,
      description: r.description || '', url: r.url || '',
      estimated_minutes: r.estimated_minutes,
    })
  }

  const retire = async (r) => {
    setError(null)
    try { await endpoints.deleteResource(r.resource_id); refresh() }
    catch (e) { setError(e.message) }
  }

  const concepts = bank.data?.concepts || []

  return (
    <div className="stack">
      <div className="grid grid-4">
        <StatCard label="Resources" value={list.data?.count ?? '-'} />
        <StatCard label="Concepts with material"
          value={new Set((list.data?.resources || []).map((r) => r.concept)).size || 0}
          hint={`of ${concepts.length} in the curriculum`} />
        <StatCard label="Total study time"
          value={minutes((list.data?.resources || []).reduce((a, r) => a + r.estimated_minutes, 0))} />
        <StatCard label="Mode" value={editingId ? 'Editing' : 'Adding'} />
      </div>

      <Card title={editingId ? `Edit resource ${editingId}` : 'Add study material'}
        subtitle="Resources are matched to students by the same concept-priority ranking that drives recommendations."
        right={editingId && (
          <button className="btn btn-sm" onClick={() => { setEditingId(null); setForm(BLANK) }}>
            Cancel
          </button>
        )}>
        <div className="grid grid-4">
          <div className="field">
            <label htmlFor="r-title">Title</label>
            <input id="r-title" value={form.title} onChange={(e) => set({ title: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="r-subject">Subject</label>
            <input id="r-subject" value={form.subject} onChange={(e) => set({ subject: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="r-concept">Concept</label>
            <select id="r-concept" value={form.concept} onChange={(e) => set({ concept: e.target.value })}>
              <option value="">Select a concept</option>
              {concepts.map((c) => <option key={c.concept} value={c.concept}>{c.label}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="r-type">Type</label>
            <select id="r-type" value={form.resource_type} onChange={(e) => set({ resource_type: e.target.value })}>
              {TYPES.map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
        </div>

        <div className="grid grid-3">
          <div className="field">
            <label htmlFor="r-difficulty">Difficulty</label>
            <select id="r-difficulty" value={form.difficulty} onChange={(e) => set({ difficulty: e.target.value })}>
              {DIFFICULTIES.map((d) => <option key={d}>{d}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="r-minutes">Estimated minutes</label>
            <input id="r-minutes" type="number" min={1} max={600} value={form.estimated_minutes}
              onChange={(e) => set({ estimated_minutes: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="r-url">URL</label>
            <input id="r-url" placeholder="https://..." value={form.url}
              onChange={(e) => set({ url: e.target.value })} />
          </div>
        </div>

        <div className="field">
          <label htmlFor="r-desc">Description</label>
          <textarea id="r-desc" rows={2} value={form.description}
            onChange={(e) => set({ description: e.target.value })} />
        </div>

        {error && <div className="notice notice-warn">{error}</div>}
        {ok && <div className="notice">{ok}</div>}

        <button className="btn btn-primary" disabled={saving || !form.title || !form.concept}
          onClick={submit}>
          {saving ? 'Saving...' : editingId ? 'Save changes' : 'Add resource'}
        </button>
      </Card>

      <Card title="Resource library">
        <Async loading={list.loading} error={list.error} onRetry={list.reload} height={160}
          label="Loading resources...">
          {list.data && (list.data.count ? (
            <div style={{ overflowX: 'auto' }}>
              <table>
                <thead>
                  <tr><th>Title</th><th>Concept</th><th>Type</th><th>Difficulty</th>
                    <th>Minutes</th><th>Status</th><th /></tr>
                </thead>
                <tbody>
                  {list.data.resources.map((r) => (
                    <tr key={r.resource_id}>
                      <td className="small">
                        {r.title}
                        {r.url && <div className="tiny muted mono" style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.url}</div>}
                      </td>
                      <td className="small">{r.label || r.concept}</td>
                      <td className="tiny">{r.resource_type}</td>
                      <td className="tiny">{r.difficulty}</td>
                      <td className="mono">{r.estimated_minutes}</td>
                      <td>{r.is_active
                        ? <span className="badge badge-low">active</span>
                        : <span className="badge badge-info">retired</span>}</td>
                      <td>
                        <div className="row" style={{ gap: '.3rem' }}>
                          <button className="btn btn-sm" onClick={() => edit(r)}>Edit</button>
                          {r.is_active !== 0 && (
                            <button className="btn btn-sm" onClick={() => retire(r)}>Retire</button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <EmptyState title="No resources yet" hint="Add study material above." />)}
        </Async>
      </Card>
    </div>
  )
}
