import { useState } from 'react'
import { api, formatDate, formatMoney } from '../api'
import { useApi } from '../hooks'
import { useAuth } from '../auth'
import { PageHeader, Card, Button, Spinner, ErrorBanner, Badge, Stepper, SuccessBanner, EmptyState } from '../components/ui'

const STEPS = [
  { value: 'draft', label: 'Draft' },
  { value: 'quotation', label: 'Quotation' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'active', label: 'Active' },
  { value: 'closed', label: 'Closed' },
]

export default function SubscriptionDetail({ id, navigate }) {
  const { user, isStaff } = useAuth()
  const { data: sub, loading, error, reload } = useApi(`/subscriptions/${id}`)
  const invoices = useApi('/invoices', { subscription_id: id, page_size: 100 })
  const [actionError, setActionError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState('')

  async function act(action) {
    setBusy(action)
    setActionError('')
    setMessage('')
    try {
      await api(`/subscriptions/${id}/transition`, { method: 'POST', body: { action } })
      setMessage(`Subscription updated: ${action}.`)
      reload()
      invoices.reload()
    } catch (err) {
      setActionError(err.message)
    } finally {
      setBusy('')
    }
  }

  if (loading && !sub) return <Spinner />
  if (error) return <ErrorBanner message={error} onRetry={reload} />
  if (!sub) return null

  const invoicePath = user.role === 'customer' ? '/portal/invoices' : '/invoices'
  const planFlags = {
    earlyClose: sub.allow_early_close,
    pause: sub.allow_pause,
    renew: sub.allow_renew,
  }

  return (
    <>
      <PageHeader
        title={sub.number}
        subtitle={`${sub.customer_name} · ${sub.plan_name} · ${sub.billing_period} billing`}
        actions={
          <Button variant="ghost" onClick={() => navigate(user.role === 'customer' ? '/portal/subscriptions' : '/subscriptions')}>
            Back to subscriptions
          </Button>
        }
      />

      <SuccessBanner message={message} />
      <ErrorBanner message={actionError} />

      <Card>
        <Stepper steps={STEPS} current={sub.status} />
      </Card>

      <div className="grid-2">
        <Card title="Subscription details">
          <dl className="detail-grid">
            <div><dt>Status</dt><dd><Badge status={sub.status}>{sub.status}</Badge></dd></div>
            <div><dt>Customer</dt><dd>{sub.customer_name}</dd></div>
            <div><dt>Plan</dt><dd>{sub.plan_name} ({sub.billing_period})</dd></div>
            <div><dt>Payment terms</dt><dd>{sub.payment_terms}</dd></div>
            <div><dt>Start date</dt><dd>{formatDate(sub.start_date)}</dd></div>
            <div><dt>Expiry date</dt><dd>{formatDate(sub.expiry_date)}</dd></div>
            <div><dt>Next billing</dt><dd>{formatDate(sub.next_billing_date)}</dd></div>
            <div><dt>Paused</dt><dd>{sub.paused ? 'Yes' : 'No'}</dd></div>
          </dl>
          {sub.notes && <p className="note-box">{sub.notes}</p>}
          <div className="flag-row">
            <span className={`flag ${planFlags.earlyClose ? 'on' : ''}`}>Early close {planFlags.earlyClose ? 'allowed' : 'blocked'}</span>
            <span className={`flag ${planFlags.pause ? 'on' : ''}`}>Pause {planFlags.pause ? 'allowed' : 'blocked'}</span>
            <span className={`flag ${planFlags.renew ? 'on' : ''}`}>Renew {planFlags.renew ? 'allowed' : 'blocked'}</span>
          </div>
        </Card>

        <Card title="Actions" subtitle="Plan flags are enforced on the server.">
          <div className="action-stack">
            {isStaff && sub.status === 'draft' && (
              <Button onClick={() => act('quotation')} disabled={Boolean(busy)}>Send quotation</Button>
            )}
            {isStaff && sub.status === 'quotation' && (
              <>
                <Button onClick={() => act('confirmed')} disabled={Boolean(busy)}>Confirm subscription</Button>
                <Button variant="ghost" onClick={() => act('draft')} disabled={Boolean(busy)}>Back to draft</Button>
              </>
            )}
            {isStaff && sub.status === 'confirmed' && (
              <Button onClick={() => act('active')} disabled={Boolean(busy)}>Activate subscription</Button>
            )}
            {sub.status === 'active' && planFlags.pause && (
              <Button variant="ghost" onClick={() => act('pause')} disabled={Boolean(busy)}>
                {sub.paused ? 'Resume subscription' : 'Pause subscription'}
              </Button>
            )}
            {sub.status === 'active' && planFlags.renew && (
              <Button variant="ghost" onClick={() => act('renew')} disabled={Boolean(busy)}>Renew for next period</Button>
            )}
            {['confirmed', 'active'].includes(sub.status) && (isStaff || planFlags.earlyClose) && (
              <Button variant="danger" onClick={() => act('closed')} disabled={Boolean(busy)}>
                Close subscription
              </Button>
            )}
            {!isStaff && !['confirmed', 'active'].includes(sub.status) && (
              <p className="muted">No customer actions are available for a {sub.status} subscription.</p>
            )}
            {!isStaff && sub.status === 'active' && !planFlags.pause && !planFlags.renew && !planFlags.earlyClose && (
              <p className="muted">This plan is locked and cannot be changed from the portal.</p>
            )}
          </div>
        </Card>
      </div>

      <Card title="Subscription lines" subtitle="Products, quantities, taxes and amounts">
        {!sub.lines?.length ? (
          <EmptyState title="No lines on this subscription" />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Variant</th>
                  <th className="num">Qty</th>
                  <th className="num">Unit price</th>
                  <th className="num">Tax</th>
                  <th className="num">Amount</th>
                </tr>
              </thead>
              <tbody>
                {sub.lines.map((line) => (
                  <tr key={line.id}>
                    <td><strong>{line.product_name}</strong></td>
                    <td>{line.variant_label || '—'}</td>
                    <td className="num">{line.quantity}</td>
                    <td className="num">{formatMoney(line.unit_price)}</td>
                    <td className="num">{line.tax_rate}%</td>
                    <td className="num">{formatMoney(line.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Invoices" subtitle="Billing history for this subscription">
        {!invoices.data?.items?.length ? (
          <EmptyState title="No invoices yet" hint="Run billing once the subscription is active." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Period</th>
                  <th>Due date</th>
                  <th className="num">Total</th>
                  <th className="num">Balance</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {invoices.data.items.map((inv) => (
                  <tr key={inv.id} className="clickable" onClick={() => navigate(`${invoicePath}/${inv.id}`)}>
                    <td><strong>{inv.number}</strong></td>
                    <td className="small">{formatDate(inv.billing_period_start)} – {formatDate(inv.billing_period_end)}</td>
                    <td className="small">{formatDate(inv.due_date)}</td>
                    <td className="num">{formatMoney(inv.total)}</td>
                    <td className="num">{formatMoney(inv.balance_due)}</td>
                    <td><Badge status={inv.status}>{inv.status}</Badge></td>
                    <td className="right">
                      <Button size="sm" variant="ghost" onClick={(e) => { e.stopPropagation(); navigate(`${invoicePath}/${inv.id}`) }}>
                        Open
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
