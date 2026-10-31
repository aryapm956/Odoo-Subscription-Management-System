import { useEffect, useState } from 'react'

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

export function Button({ variant = 'primary', size = 'md', type = 'button', className = '', loading = false, children, disabled, ...props }) {
  return (
    <button
      type={type}
      className={`btn btn-${variant} btn-${size} ${className}`}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading && <span className="button-spinner" aria-hidden="true" />}
      {children}
    </button>
  )
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
    <div className="loading loading-skeleton" role="status" aria-label={label} aria-busy="true">
      <span className="skeleton skeleton-heading" />
      <span className="skeleton skeleton-line" />
      <div className="skeleton-table">
        {Array.from({ length: 5 }, (_, index) => <span className="skeleton skeleton-row" key={index} />)}
      </div>
    </div>
  )
}

export function AnimatedNumber({ value, currency = false, duration = 800 }) {
  const target = Number(value) || 0
  const [displayValue, setDisplayValue] = useState(0)
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

  useEffect(() => {
    if (reducedMotion) return undefined

    let frame
    const startedAt = performance.now()
    const animate = (now) => {
      const progress = Math.min(1, (now - startedAt) / duration)
      const eased = 1 - (1 - progress) ** 3
      setDisplayValue(target * eased)
      if (progress < 1) frame = requestAnimationFrame(animate)
    }
    frame = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(frame)
  }, [target, duration, reducedMotion])

  const shownValue = reducedMotion ? target : displayValue

  return (
    <span>
      {currency
        ? `₹${shownValue.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
        : Math.round(shownValue).toLocaleString('en-IN')}
    </span>
  )
}

export function Toast({ message, onClose, duration = 4500 }) {
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    if (!message) return undefined
    const timeout = window.setTimeout(() => {
      setVisible(false)
    }, duration)
    return () => window.clearTimeout(timeout)
  }, [message, duration])

  if (!message || !visible) return null
  return (
    <div className="toast" role="status">
      <span>{message}</span>
      <button className="icon-btn" onClick={() => { setVisible(false); onClose?.() }} aria-label="Dismiss notification">×</button>
      <span className="toast-progress" style={{ animationDuration: `${duration}ms` }} />
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
    <div className="stepper">
      <div className="stepper-line" aria-hidden="true">
        <span style={{ width: `${steps.length > 1 ? Math.max(0, currentIndex) / (steps.length - 1) * 100 : 0}%` }} />
      </div>
      <ol className="stepper-steps">
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
    </div>
  )
}
