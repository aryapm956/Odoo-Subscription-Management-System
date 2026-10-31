import { useEffect } from 'react'

export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  )
}

export function Card({ title, subtitle, actions, children, className = '' }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="card-head">
          <div>
            {title && <h2>{title}</h2>}
            {subtitle && <p className="muted small">{subtitle}</p>}
          </div>
          {actions && <div className="card-actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  )
}

export function Button({ variant = 'primary', size = 'md', type = 'button', className = '', ...props }) {
  return <button type={type} className={`btn btn-${variant} btn-${size} ${className}`} {...props} />
}

export function Field({ label, hint, children, className = '' }) {
  return (
    <label className={`field ${className}`}>
      {label && <span className="field-label">{label}</span>}
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  )
}

const STATUS_TONES = {
  draft: 'gray',
  quotation: 'blue',
  confirmed: 'amber',
  active: 'green',
  closed: 'gray',
  paid: 'green',
  cancelled: 'red',
  overdue: 'red',
  expired: 'red',
  exhausted: 'red',
  scheduled: 'blue',
}

export function Badge({ status, children }) {
  const key = String(status || '').toLowerCase()
  return <span className={`badge badge-${STATUS_TONES[key] || 'gray'}`}>{children || key}</span>
}

export function Pagination({ page, pageSize, total, onPage }) {
  const pages = Math.max(1, Math.ceil((total || 0) / (pageSize || 1)))
  if (pages <= 1) return null
  return (
    <div className="pagination">
      <Button variant="ghost" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        Previous
      </Button>
      <span className="muted small">
        Page {page} of {pages} · {total} total
      </span>
      <Button variant="ghost" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
        Next
      </Button>
    </div>
  )
}

export function Spinner({ label = 'Loading…' }) {
  return (
    <div className="loading">
      <span className="spinner" />
      <span className="muted">{label}</span>
    </div>
  )
}

export function ErrorBanner({ message, onRetry }) {
  if (!message) return null
  return (
    <div className="alert alert-error">
      <span>{message}</span>
      {onRetry && (
        <Button variant="ghost" size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  )
}

export function SuccessBanner({ message }) {
  if (!message) return null
  return <div className="alert alert-success">{message}</div>
}

export function EmptyState({ title = 'Nothing here yet', hint }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">◌</div>
      <h3>{title}</h3>
      {hint && <p className="muted">{hint}</p>}
    </div>
  )
}

export function Modal({ open, onClose, title, children, footer, wide = false }) {
  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? 'modal-wide' : ''}`} role="dialog" aria-modal="true">
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  )
}

export function Tabs({ tabs, value, onChange }) {
  return (
    <div className="tabs">
      {tabs.map((tab) => (
        <button
          key={tab.value}
          className={`tab ${value === tab.value ? 'active' : ''}`}
          onClick={() => onChange(tab.value)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}

export function Stepper({ steps, current }) {
  const currentIndex = steps.findIndex((s) => s.value === current)
  return (
    <ol className="stepper">
      {steps.map((step, idx) => {
        const state = idx < currentIndex ? 'done' : idx === currentIndex ? 'current' : 'todo'
        return (
          <li key={step.value} className={`step step-${state}`}>
            <span className="step-dot">{idx < currentIndex ? '✓' : idx + 1}</span>
            <span>{step.label}</span>
          </li>
        )
      })}
    </ol>
  )
}
