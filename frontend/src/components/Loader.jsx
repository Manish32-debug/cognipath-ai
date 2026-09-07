/** Loading, error and empty states. Every async panel in the app uses these so
 *  the UI degrades predictably instead of crashing or showing a blank box. */
export function Spinner({ label }) {
  return (
    <div className="row" style={{ padding: '.4rem 0' }}>
      <div className="spinner" />
      <span className="small muted">{label || 'Loading...'}</span>
    </div>
  )
}

export function Skeleton({ height = 90, count = 1 }) {
  return (
    <div className="stack">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height }} />
      ))}
    </div>
  )
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="card" style={{ borderColor: 'rgba(248,113,113,.4)' }}>
      <h3 style={{ color: 'var(--bad)' }}>Something went wrong</h3>
      <p className="small">{message}</p>
      {onRetry && <button className="btn btn-sm" onClick={onRetry}>Try again</button>}
    </div>
  )
}

export function EmptyState({ title, hint }) {
  return (
    <div className="card center">
      <h3>{title}</h3>
      <p className="small">{hint}</p>
    </div>
  )
}

/** Wraps a panel: shows a labelled skeleton while loading, an error card on
 *  failure, and the children once data has arrived. */
export function Async({ loading, error, onRetry, label, height, children }) {
  if (loading) {
    return (
      <div className="stack">
        <Spinner label={label} />
        <Skeleton height={height || 110} />
      </div>
    )
  }
  if (error) return <ErrorState message={error} onRetry={onRetry} />
  return children
}
