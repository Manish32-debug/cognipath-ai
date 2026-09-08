import { useState } from 'react'
import { Card, StatCard } from '../../components/Card.jsx'
import { Async, EmptyState } from '../../components/Loader.jsx'
import { useApi } from '../../hooks/useApi.js'
import { endpoints } from '../../services/api.js'

const DIFFICULTIES = ['Easy', 'Medium', 'Hard']
const MAX_MB = 10

export default function TeacherSamplePapers() {
  const [nonce, setNonce] = useState(0)
  const list = useApi(() => endpoints.samplePapers(), [nonce])

  const [file, setFile] = useState(null)
  const [meta, setMeta] = useState({
    title: '', subject: 'Mathematics', difficulty: 'Medium',
    year: new Date().getFullYear(), semester: '', description: '',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [ok, setOk] = useState(null)

  const set = (patch) => setMeta((m) => ({ ...m, ...patch }))

  const pick = (e) => {
    const f = e.target.files?.[0] || null
    setError(null); setOk(null)
    if (!f) { setFile(null); return }
    if (f.type !== 'application/pdf') { setError('Only PDF files are accepted.'); setFile(null); return }
    if (f.size > MAX_MB * 1024 * 1024) { setError(`PDF must be under ${MAX_MB} MB.`); setFile(null); return }
    setFile(f)
  }

  const upload = async () => {
    setBusy(true); setError(null); setOk(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('title', meta.title)
      fd.append('subject', meta.subject)
      fd.append('difficulty', meta.difficulty)
      if (meta.year) fd.append('year', String(meta.year))
      if (meta.semester) fd.append('semester', meta.semester)
      if (meta.description) fd.append('description', meta.description)
      await endpoints.uploadSamplePaper(fd)
      setOk('Paper uploaded.')
      setFile(null)
      setMeta((m) => ({ ...m, title: '', description: '' }))
      setNonce((n) => n + 1)
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const remove = async (p) => {
    setError(null)
    try { await endpoints.deleteSamplePaper(p.paper_id); setNonce((n) => n + 1) }
    catch (e) { setError(e.message) }
  }

  const view = async (p, download) => {
    setError(null)
    try {
      const blob = await endpoints.samplePaperBlob(p.paper_id)
      const url = URL.createObjectURL(blob)
      if (download) {
        const a = document.createElement('a')
        a.href = url; a.download = p.filename || `${p.title}.pdf`
        document.body.appendChild(a); a.click(); a.remove()
      } else window.open(url, '_blank', 'noopener')
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch (e) { setError(e.message) }
  }

  const papers = list.data?.papers || []

  return (
    <div className="stack">
      <div className="grid grid-4">
        <StatCard label="Papers" value={list.data?.count ?? '-'} />
        <StatCard label="Demo placeholders" value={papers.filter((p) => p.is_demo).length} />
        <StatCard label="Uploaded by staff" value={papers.filter((p) => !p.is_demo).length} />
        <StatCard label="Total size"
          value={`${Math.round(papers.reduce((a, p) => a + p.size_bytes, 0) / 1024)} KB`} />
      </div>

      <div className="notice notice-warn">
        Uploaded PDFs are stored inside the SQLite database. On a Render instance
        without a persistent disk that database is rebuilt on every deploy, so
        staff uploads do not survive a redeploy. Seeded demo papers are recreated
        automatically; uploads are not.
      </div>

      <Card title="Upload a sample paper" subtitle={`PDF only, up to ${MAX_MB} MB.`}>
        <div className="grid grid-3">
          <div className="field">
            <label htmlFor="p-title">Title</label>
            <input id="p-title" value={meta.title} onChange={(e) => set({ title: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="p-subject">Subject</label>
            <input id="p-subject" value={meta.subject} onChange={(e) => set({ subject: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="p-difficulty">Difficulty</label>
            <select id="p-difficulty" value={meta.difficulty} onChange={(e) => set({ difficulty: e.target.value })}>
              {DIFFICULTIES.map((d) => <option key={d}>{d}</option>)}
            </select>
          </div>
        </div>
        <div className="grid grid-3">
          <div className="field">
            <label htmlFor="p-year">Year</label>
            <input id="p-year" type="number" value={meta.year} onChange={(e) => set({ year: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="p-semester">Semester</label>
            <input id="p-semester" value={meta.semester} onChange={(e) => set({ semester: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="p-file">PDF file</label>
            <input id="p-file" type="file" accept="application/pdf" onChange={pick} />
          </div>
        </div>
        <div className="field">
          <label htmlFor="p-desc">Description</label>
          <textarea id="p-desc" rows={2} value={meta.description}
            onChange={(e) => set({ description: e.target.value })} />
        </div>

        {error && <div className="notice notice-warn">{error}</div>}
        {ok && <div className="notice">{ok}</div>}

        <button className="btn btn-primary" disabled={busy || !file || !meta.title} onClick={upload}>
          {busy ? 'Uploading...' : 'Upload paper'}
        </button>
      </Card>

      <Card title="Sample papers">
        <Async loading={list.loading} error={list.error} onRetry={list.reload} height={140}
          label="Loading papers...">
          {list.data && (list.data.count ? (
            <div style={{ overflowX: 'auto' }}>
              <table>
                <thead>
                  <tr><th>Title</th><th>Subject</th><th>Year</th><th>Difficulty</th>
                    <th>Size</th><th>Origin</th><th /></tr>
                </thead>
                <tbody>
                  {papers.map((p) => (
                    <tr key={p.paper_id}>
                      <td className="small">{p.title}</td>
                      <td className="small">{p.subject}</td>
                      <td className="mono">{p.year || '-'}</td>
                      <td className="tiny">{p.difficulty}</td>
                      <td className="mono tiny">{Math.round(p.size_bytes / 1024)} KB</td>
                      <td>{p.is_demo
                        ? <span className="badge badge-info">demo placeholder</span>
                        : <span className="badge badge-low">uploaded</span>}</td>
                      <td>
                        <div className="row" style={{ gap: '.3rem' }}>
                          <button className="btn btn-sm" onClick={() => view(p, false)}>View</button>
                          <button className="btn btn-sm" onClick={() => view(p, true)}>Download</button>
                          <button className="btn btn-sm" onClick={() => remove(p)}>Delete</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <EmptyState title="No papers" hint="Upload a PDF above." />)}
        </Async>
      </Card>
    </div>
  )
}
