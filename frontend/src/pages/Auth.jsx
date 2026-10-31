import { useEffect, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import { Button, Field, ErrorBanner, SuccessBanner, Spinner } from '../components/ui'

export function passwordErrors(password) {
  const errors = []
  if (password.length <= 8) errors.push('More than 8 characters')
  if (!/[A-Z]/.test(password)) errors.push('One uppercase letter')
  if (!/[a-z]/.test(password)) errors.push('One lowercase letter')
  if (!/[^a-zA-Z0-9]/.test(password)) errors.push('One special character')
  return errors
}

function AuthLayout({ title, subtitle, children, footer }) {
  return (
    <div className="auth-page">
      <div className="auth-panel">
        <div className="auth-brand">
          <span className="brand-mark large">B</span>
          <div>
            <h1>Brightloop</h1>
            <p>One system to run plans, subscriptions and recurring billing.</p>
          </div>
        </div>
        <div className="auth-points">
          <div>
            <strong>Recurring billing</strong>
            <span>Invoices generated on time, every time.</span>
          </div>
          <div>
            <strong>Live revenue</strong>
            <span>MRR, collections and overdue balances in one view.</span>
          </div>
          <div>
            <strong>Customer portal</strong>
            <span>Customers manage their own subscriptions.</span>
          </div>
        </div>
      </div>
      <div className="auth-card">
        <div className="auth-card-inner">
          <h2>{title}</h2>
          <p className="muted auth-sub">{subtitle}</p>
          {children}
          {footer && <div className="auth-footer">{footer}</div>}
        </div>
      </div>
    </div>
  )
}

export function LoginPage({ navigate }) {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const user = await login(email.trim(), password)
      navigate(user.role === 'customer' ? '/portal/subscriptions' : '/dashboard')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to your Brightloop workspace."
      footer={
        <>
          New here?{' '}
          <button className="link" onClick={() => navigate('/signup')}>
            Create an account
          </button>
        </>
      }
    >
      <form onSubmit={submit} className="form-stack">
        <ErrorBanner message={error} />
        <Field label="Email">
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" placeholder="you@company.com" />
        </Field>
        <Field label="Password">
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" placeholder="•••••••••" />
        </Field>
        <div className="row-between">
          <button type="button" className="link small" onClick={() => navigate('/forgot-password')}>
            Forgot password?
          </button>
        </div>
        <Button type="submit" disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </Button>
        <div className="demo-box">
          <strong>Demo logins</strong>
          <span>admin@brightloop.com / Admin@12345</span>
          <span>staff@brightloop.com / Staff@12345</span>
          <span>customer@brightloop.com / Customer@12345</span>
        </div>
      </form>
    </AuthLayout>
  )
}

export function SignupPage({ navigate }) {
  const { signup } = useAuth()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const rules = passwordErrors(password)

  async function submit(e) {
    e.preventDefault()
    setError('')
    if (rules.length) {
      setError(`Password needs: ${rules.join(', ')}.`)
      return
    }
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    setBusy(true)
    try {
      await signup(name.trim(), email.trim(), password)
      navigate('/portal/subscriptions')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Start managing your subscriptions in minutes."
      footer={
        <>
          Already have an account?{' '}
          <button className="link" onClick={() => navigate('/login')}>
            Sign in
          </button>
        </>
      }
    >
      <form onSubmit={submit} className="form-stack">
        <ErrorBanner message={error} />
        <Field label="Full name">
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} required placeholder="Jane Cooper" />
        </Field>
        <Field label="Email">
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" placeholder="you@company.com" />
        </Field>
        <Field label="Password" hint="More than 8 characters, with uppercase, lowercase and a special character.">
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="new-password" />
        </Field>
        {password && (
          <div className="rule-list">
            {[
              ['More than 8 characters', password.length > 8],
              ['Uppercase letter', /[A-Z]/.test(password)],
              ['Lowercase letter', /[a-z]/.test(password)],
              ['Special character', /[^a-zA-Z0-9]/.test(password)],
            ].map(([label, ok]) => (
              <span key={label} className={ok ? 'rule ok' : 'rule'}>
                {ok ? '✓' : '○'} {label}
              </span>
            ))}
          </div>
        )}
        <Field label="Confirm password">
          <input className="input" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required autoComplete="new-password" />
        </Field>
        <Button type="submit" disabled={busy}>
          {busy ? 'Creating account…' : 'Create account'}
        </Button>
      </form>
    </AuthLayout>
  )
}

export function ForgotPasswordPage({ navigate }) {
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await api('/auth/forgot-password', { method: 'POST', body: { email: email.trim() }, auth: false })
      setMessage('If that email is registered, a reset link has been sent. Check the dev outbox if SMTP is not configured.')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout
      title="Reset your password"
      subtitle="We will send a single-use, time-limited reset link."
      footer={
        <button className="link" onClick={() => navigate('/login')}>
          Back to sign in
        </button>
      }
    >
      <form onSubmit={submit} className="form-stack">
        <ErrorBanner message={error} />
        <SuccessBanner message={message} />
        <Field label="Registered email">
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required placeholder="you@company.com" />
        </Field>
        <Button type="submit" disabled={busy}>
          {busy ? 'Sending…' : 'Send reset link'}
        </Button>
        <button type="button" className="link small" onClick={() => navigate('/dev-outbox')}>
          Open dev outbox
        </button>
      </form>
    </AuthLayout>
  )
}

export function ResetPasswordPage({ navigate, params }) {
  const token = params?.get('token') || ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const rules = passwordErrors(password)

  async function submit(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    if (!token) {
      setError('This reset link is missing its token. Request a new link.')
      return
    }
    if (rules.length) {
      setError(`Password needs: ${rules.join(', ')}.`)
      return
    }
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    setBusy(true)
    try {
      await api('/auth/reset-password', { method: 'POST', body: { token, password }, auth: false })
      setMessage('Password reset successfully. You can now sign in.')
      setTimeout(() => navigate('/login'), 1200)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout
      title="Choose a new password"
      subtitle="Reset links are single-use and expire automatically."
      footer={
        <button className="link" onClick={() => navigate('/login')}>
          Back to sign in
        </button>
      }
    >
      <form onSubmit={submit} className="form-stack">
        <ErrorBanner message={error} />
        <SuccessBanner message={message} />
        {!token && <ErrorBanner message="No reset token found in the link." />}
        <Field label="New password">
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </Field>
        <Field label="Confirm new password">
          <input className="input" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
        </Field>
        <Button type="submit" disabled={busy || !token}>
          {busy ? 'Resetting…' : 'Reset password'}
        </Button>
      </form>
    </AuthLayout>
  )
}

export function DevOutboxPage({ navigate }) {
  const [emails, setEmails] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function load() {
    setLoading(true)
    setError('')
    try {
      setEmails(await api('/auth/dev/outbox', { auth: false }))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <div className="standalone-page">
      <div className="standalone-head">
        <div>
          <h1>Dev email outbox</h1>
          <p className="muted">Simulated emails appear here when SMTP is not configured.</p>
        </div>
        <div className="page-actions">
          <Button variant="ghost" onClick={() => navigate('/login')}>
            Back
          </Button>
          <Button onClick={load}>Refresh</Button>
        </div>
      </div>
      <ErrorBanner message={error} />
      {loading && <Spinner />}
      {emails && emails.length === 0 && <div className="alert">No emails yet. Request a password reset to see one here.</div>}
      <div className="outbox-list">
        {(emails || []).map((mail) => {
          const link = (mail.html || '').match(/href="([^"]+)"/)?.[1]
          return (
            <div className="card outbox-item" key={mail.id}>
              <div className="row-between">
                <strong>{mail.subject}</strong>
                <span className="muted small">{new Date(mail.sent_at).toLocaleString()}</span>
              </div>
              <div className="muted small">To: {mail.to}</div>
              {link && (
                <div className="outbox-link">
                  <span className="muted small">Action link:</span>
                  <a href={link}>{link}</a>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
