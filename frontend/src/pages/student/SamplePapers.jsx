import { useState } from 'react'
import { Card } from '../../components/Card.jsx'
import { Async, EmptyState } from '../../components/Loader.jsx'
import { useApi } from '../../hooks/useApi.js'
import { endpoints } from '../../services/api.js'

const DIFFICULTY_CLASS = { Easy: 'badge badge-low', Medium: 'badge badge-med', Hard: 'badge badge-high' }

/** Papers are served from an authenticated endpoint, so a plain href would 401.
 *  Fetch as a blob through the axios instance (which attaches the bearer token)
 *  and hand the browser an object URL. */
function usePaperFile() {
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)

  const open = async (paper, download) => {
    setBusy(paper.paper_id); setError(null)
    try {
      const blob = await endpoints.samplePaperBlob(paper.paper_id)
      const url = URL.createObjectURL(blob)
      if (download) {
        const a = document.createElement('a')
        a.href = url
        a.download = paper.filename || `${paper.title}.pdf`
        document.body.appendChild(a)
        a.click()
        a.remove()
      } else {
        window.open(url, '_blank', 'noopener')
      }
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch (e) { setError(e.message) } finally { setBusy(null) }
  }

  return { open, busy, error }
}

export default function SamplePapers() {
  const { data, error, loading, reload } = useApi(() => endpoints.samplePapers(), [])
  const file = usePaperFile()

  return (
    <div className="stack">
      <Async loading={loading} error={error} onRetry={reload} height={160}
        label="Loading sample papers...">
        {data && (data.count ? (
          <>
            <div className="notice">{data.note}</div>
            {file.error && <div className="notice notice-warn">{file.error}</div>}

            {data.by_subject.map((group) => (
              <Card key={group.subject} title={group.subject}
                right={<span className="chip">{group.papers.length} paper(s)</span>}>
                <div className="stack" style={{ gap: '.45rem' }}>
                  {group.papers.map((p) => (
                    <div key={p.paper_id} className="between"
                      style={{ padding: '.6rem', border: '1px solid var(--border)', borderRadius: 8 }}>
                      <span>
                        <b className="small">{p.title}</b>
                        <div className="row wrap" style={{ gap: '.35rem', marginTop: '.3rem' }}>
                          <span className={DIFFICULTY_CLASS[p.difficulty]}>{p.difficulty}</span>
                          {p.year && <span className="chip">{p.year}</span>}
                          {p.semester && <span className="chip">{p.semester}</span>}
                          {p.is_demo && <span className="badge badge-info">demo placeholder</span>}
                          <span className="tiny muted">{Math.round(p.size_bytes / 1024)} KB</span>
                        </div>
                        {p.description && <div className="tiny muted" style={{ marginTop: '.35rem' }}>{p.description}</div>}
                      </span>
                      <span className="row" style={{ gap: '.4rem' }}>
                        <button className="btn btn-sm" disabled={file.busy === p.paper_id}
                          onClick={() => file.open(p, false)}>View PDF</button>
                        <button className="btn btn-sm" disabled={file.busy === p.paper_id}
                          onClick={() => file.open(p, true)}>Download</button>
                      </span>
                    </div>
                  ))}
                </div>
              </Card>
            ))}
          </>
        ) : (
          <EmptyState title="No sample papers yet"
            hint="A teacher can upload PDFs from the teacher dashboard." />
        ))}
      </Async>
    </div>
  )
}
