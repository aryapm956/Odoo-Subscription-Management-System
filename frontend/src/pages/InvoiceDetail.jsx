import { useState } from 'react'
import { api, formatDate, formatMoney, todayISO } from '../api'
import { useApi } from '../hooks'
import { useAuth } from '../auth'
import { PageHeader, Card, Button, Field, Modal, Spinner, ErrorBanner, Badge, EmptyState, Toast } from '../components/ui'

const METHODS = ['card', 'bank_transfer', 'cash', 'upi', 'cheque', 'other']

export default function InvoiceDetail({ id, navigate }) {
  const { user, isStaff } = useAuth()
  const { data: invoice, loading, error, reload } = useApi(`/invoices/${id}`)
  const [payOpen, setPayOpen] = useState(false)
  const [payment, setPayment] = useState({ method: 'bank_transfer', amount: '', date: todayISO(), note: '' })
  const [message, setMessage] = useState('')
  const [actionError, setActionError] = useState('')
  const [busy, setBusy] = useState('')
  const [confetti, setConfetti] = useState(false)

  async function action(name, fn) {
    setBusy(name)
    setActionError('')
    setMessage('')
    try {
      await fn()
      setMessage(`${name} successful.`)
      reload()
    } catch (err) {
      setActionError(err.message)
    } finally {
      setBusy('')
    }
  }

  function openPayment() {
    setMessage('')
    setPayment({ method: 'bank_transfer', amount: invoice?.balance_due ? String(invoice.balance_due) : '', date: todayISO(), note: '' })
    setActionError('')
    setPayOpen(true)
  }

  async function submitPayment(e) {
    e.preventDefault()
    setActionError('')
    const amount = Number(payment.amount)
    if (!amount || amount <= 0) {
      setActionError('Payment amount must be positive.')
      return
    }
    if (amount > Number(invoice.balance_due)) {
      setActionError(`Payment cannot exceed the balance of ${formatMoney(invoice.balance_due)}.`)
      return
    }
    setBusy('payment')
    try {
      await api(`/invoices/${id}/payments`, {
        method: 'POST',
        body: { method: payment.method, amount, date: payment.date, note: payment.note || null },
      })
      setPayOpen(false)
      setMessage('Payment recorded.')
      if (amount >= Number(invoice.balance_due) - 0.01) {
        setConfetti(true)
        window.setTimeout(() => setConfetti(false), 500)
      }
      reload()
    } catch (err) {
      setActionError(err.message)
    } finally {
      setBusy('')
    }
  }

  if (loading && !invoice) return <Spinner />
  if (error) return <ErrorBanner message={error} onRetry={reload} />
  if (!invoice) return null

  const backPath = user.role === 'customer' ? '/portal/invoices' : '/invoices'
  const canCancel = isStaff && ['draft', 'confirmed'].includes(invoice.status) && Number(invoice.amount_paid) === 0
  const canPay = isStaff && invoice.status === 'confirmed' && Number(invoice.balance_due) > 0

  return (
    <>
      <PageHeader
        title={invoice.number}
        subtitle={`${invoice.customer_name} · ${invoice.subscription_number || 'No subscription'}`}
        actions={
          <>
            <Button variant="ghost" onClick={() => navigate(backPath)}>Back</Button>
            <Button variant="ghost" onClick={() => window.print()}>Print</Button>
          </>
        }
      />

      <Toast key={message || 'no-message'} message={message} onClose={() => setMessage('')} />
      <ErrorBanner message={actionError} />
      {confetti && (
        <div className="confetti-burst" aria-hidden="true">
          {Array.from({ length: 18 }, (_, index) => (
            <span
              key={index}
              style={{
                '--confetti-index': index,
                '--confetti-x': `${(index % 6 - 2.5) * 28}px`,
                '--confetti-y': `${-35 - Math.floor(index / 6) * 24}px`,
              }}
            />
          ))}
        </div>
      )}

      {isStaff && (
        <Card title="Invoice actions" subtitle="Status changes are validated by the server.">
          <div className="action-row">
            {invoice.status === 'draft' && (
              <Button onClick={() => action('Confirm', () => api(`/invoices/${id}/confirm`, { method: 'POST' }))} disabled={Boolean(busy)} loading={busy === 'Confirm'}>
                Confirm invoice
              </Button>
            )}
            {invoice.status !== 'draft' && invoice.status !== 'cancelled' && (
              <Button variant="ghost" onClick={() => action('Send', () => api(`/invoices/${id}/send`, { method: 'POST' }))} disabled={Boolean(busy)} loading={busy === 'Send'}>
                Send by email
              </Button>
            )}
            {canPay && <Button onClick={openPayment} disabled={Boolean(busy)}>Record payment</Button>}
            {canCancel && (
              <Button variant="danger" onClick={() => action('Cancel', () => api(`/invoices/${id}/cancel`, { method: 'POST' }))} disabled={Boolean(busy)} loading={busy === 'Cancel'}>
                Cancel invoice
              </Button>
            )}
            {!canCancel && invoice.status === 'confirmed' && Number(invoice.amount_paid) > 0 && (
              <span className="muted small">This invoice has payments and cannot be cancelled.</span>
            )}
            {invoice.status === 'paid' && <span className="muted small">Fully paid. No further action needed.</span>}
            {invoice.status === 'cancelled' && <span className="muted small">Cancelled invoices are excluded from revenue.</span>}
          </div>
        </Card>
      )}

      <div className="invoice-print">
        <Card className="invoice-card">
          <div className="invoice-head">
            <div>
              <div className="invoice-brand"><span className="brand-mark">B</span> Brightloop Software</div>
              <p className="muted small">Subscription billing statement</p>
            </div>
            <div className="invoice-meta">
              <Badge status={invoice.is_overdue ? 'overdue' : invoice.status}>{invoice.is_overdue ? 'overdue' : invoice.status}</Badge>
              <h2>{invoice.number}</h2>
              <div className="muted small">Issued {formatDate(invoice.issue_date)}</div>
              <div className="muted small">Due {formatDate(invoice.due_date)}</div>
              {invoice.is_overdue && <div className="overdue-text">{invoice.days_overdue} days overdue</div>}
            </div>
          </div>

          <div className="invoice-parties">
            <div>
              <span className="label">Billed to</span>
              <strong>{invoice.customer_name}</strong>
              <div className="muted small">Customer #{invoice.customer_id}</div>
            </div>
            <div>
              <span className="label">Billing period</span>
              <strong>{formatDate(invoice.billing_period_start)} – {formatDate(invoice.billing_period_end)}</strong>
              <div className="muted small">Subscription {invoice.subscription_number || '—'}</div>
            </div>
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Description</th>
                  <th className="num">Qty</th>
                  <th className="num">Unit price</th>
                  <th className="num">Tax</th>
                  <th className="num">Discount</th>
                  <th className="num">Amount</th>
                </tr>
              </thead>
              <tbody>
                {invoice.lines.map((line) => (
                  <tr key={line.id}>
                    <td>{line.description}</td>
                    <td className="num">{line.quantity}</td>
                    <td className="num">{formatMoney(line.unit_price)}</td>
                    <td className="num">{line.tax_rate}%</td>
                    <td className="num">{formatMoney(line.discount)}</td>
                    <td className="num">{formatMoney(line.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="invoice-totals">
            <div><span>Subtotal</span><strong>{formatMoney(invoice.subtotal)}</strong></div>
            <div><span>Discounts</span><strong>− {formatMoney(invoice.discount_total)}</strong></div>
            <div><span>Tax</span><strong>{formatMoney(invoice.tax_total)}</strong></div>
            <div className="grand"><span>Total</span><strong>{formatMoney(invoice.total)}</strong></div>
            <div><span>Paid</span><strong>{formatMoney(invoice.amount_paid)}</strong></div>
            <div className={Number(invoice.balance_due) > 0 ? 'due' : ''}><span>Balance due</span><strong>{formatMoney(invoice.balance_due)}</strong></div>
          </div>
        </Card>
      </div>

      <Card title="Payments" subtitle="Partial payments are supported; overpayment is blocked.">
        {!invoice.payments?.length ? (
          <EmptyState title="No payments recorded" hint={canPay ? 'Record the first payment above.' : undefined} />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Method</th>
                  <th className="num">Amount</th>
                  <th>Note</th>
                </tr>
              </thead>
              <tbody>
                {invoice.payments.map((p) => (
                  <tr key={p.id}>
                    <td>{formatDate(p.date)}</td>
                    <td><Badge status="quotation">{p.method.replace('_', ' ')}</Badge></td>
                    <td className="num">{formatMoney(p.amount)}</td>
                    <td className="small">{p.note || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Modal
        open={payOpen}
        onClose={() => setPayOpen(false)}
        title={`Record payment · ${invoice.number}`}
        footer={
          <>
            <Button variant="ghost" onClick={() => setPayOpen(false)}>Cancel</Button>
            <Button onClick={submitPayment} loading={busy === 'payment'}>{busy === 'payment' ? 'Recording…' : 'Record payment'}</Button>
          </>
        }
      >
        <form onSubmit={submitPayment} className="form-stack">
          <ErrorBanner message={actionError} />
          <div className="payment-balance">
            <span className="muted small">Outstanding balance</span>
            <strong>{formatMoney(invoice.balance_due)}</strong>
          </div>
          <div className="grid-2">
            <Field label="Method">
              <select className="input" value={payment.method} onChange={(e) => setPayment({ ...payment, method: e.target.value })}>
                {METHODS.map((m) => <option key={m} value={m}>{m.replace('_', ' ')}</option>)}
              </select>
            </Field>
            <Field label="Amount">
              <input className="input" type="number" min="0.01" step="0.01" max={invoice.balance_due} value={payment.amount} onChange={(e) => setPayment({ ...payment, amount: e.target.value })} required />
            </Field>
            <Field label="Payment date">
              <input className="input" type="date" value={payment.date} onChange={(e) => setPayment({ ...payment, date: e.target.value })} required />
            </Field>
            <Field label="Note">
              <input className="input" value={payment.note} onChange={(e) => setPayment({ ...payment, note: e.target.value })} placeholder="Reference or memo" />
            </Field>
          </div>
        </form>
      </Modal>
    </>
  )
}
