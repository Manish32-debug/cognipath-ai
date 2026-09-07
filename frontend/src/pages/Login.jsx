import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      const me = await login(form.username.trim().toLowerCase(), form.password)
      const target = location.state?.from || (me.role === 'teacher' ? '/teacher' : '/app')
      navigate(target, { replace: true })
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const quick = (username, password) => setForm({ username, password })

  return (
    <div className="container" style={{ maxWidth: 460, paddingTop: '6vh' }}>
      <Link to="/" className="brand" style={{ marginBottom: '1.4rem' }}>
        <span className="brand-mark">CP</span> CogniPath<span style={{ color: 'var(--brand-2)' }}> AI</span>
      </Link>

      <div className="card">
        <h2>Sign in</h2>
        <p className="small">Role-based access: students see only their own record, teachers see the cohort.</p>

        <form onSubmit={submit}>
          <div className="field">
            <label htmlFor="username">Username</label>
            <input id="username" autoComplete="username" value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })} required />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input id="password" type="password" autoComplete="current-password" value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })} required />
          </div>
          {error && <div className="notice notice-warn" style={{ marginBottom: '.8rem' }}>{error}</div>}
          <button className="btn btn-primary" style={{ width: '100%' }} disabled={busy}>
            {busy ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        <div className="notice" style={{ marginTop: '1rem' }}>
          <b>Demo accounts</b> (seeded by <span className="mono">python -m app.database.seed</span>)
          <div className="row wrap" style={{ marginTop: '.5rem' }}>
            <button className="btn btn-sm" type="button" onClick={() => quick('demo001', 'demo1234')}>Student demo001</button>
            <button className="btn btn-sm" type="button" onClick={() => quick('teacher', 'teach1234')}>Teacher</button>
          </div>
        </div>
      </div>
    </div>
  )
}
