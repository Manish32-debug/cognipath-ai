import { NavLink } from 'react-router-dom'

export default function Sidebar({ items, footer }) {
  return (
    <aside className="sidebar">
      <div className="brand" style={{ padding: '.4rem .5rem 1rem' }}>
        <span className="brand-mark">CP</span>
        <span>CogniPath<span style={{ color: 'var(--brand-2)' }}> AI</span></span>
      </div>
      <nav className="stack" style={{ gap: '.15rem' }}>
        {items.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.end}
            className={({ isActive }) => `side-link ${isActive ? 'active' : ''}`}>
            <span aria-hidden>{item.icon}</span>{item.label}
          </NavLink>
        ))}
      </nav>
      {footer && <div className="tiny muted" style={{ marginTop: '1.2rem', padding: '0 .6rem' }}>{footer}</div>}
    </aside>
  )
}
