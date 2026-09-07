import { useCallback, useEffect, useState } from 'react'

/** Runs an async function on mount (and when `deps` change). */
export function useApi(fn, deps = [], { enabled = true } = {}) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(enabled)
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return
    }

    let cancelled = false

    setLoading(true)
    setError(null)

    fn()
      .then((d) => {
        if (!cancelled) {
          setData(d)
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e.message || String(e))
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled, nonce])

  const reload = useCallback(() => {
    setNonce((n) => n + 1)
  }, [])

  return { data, error, loading, reload }
}