import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { initials } from '../utils/format.js'

export default function Navbar({ title, subtitle, notice }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <header className="topbar">
      <div>
        <div className="row">
          <strong>{title}</strong>
          {notice && <span className="chip">{notice}</span>}
        </div>
        {subtitle && <div className="tiny muted">{subtitle}</div>}
      </div>
      <div className="row">
        <Link to="/" className="btn btn-sm btn-ghost">Home</Link>
        <div className="avatar" title={user?.username}>{initials(user?.username)}</div>
        <div className="tiny muted" style={{ minWidth: 0 }}>
          <div>{user?.username}</div>
          <div style={{ textTransform: 'capitalize' }}>{user?.role}</div>
        </div>
        <button className="btn btn-sm" onClick={() => { logout(); navigate('/login') }}>Sign out</button>
      </div>
    </header>
  )
}
