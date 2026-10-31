import { useState } from 'react'
import { api, formatMoney, formatDate } from '../api'
import { useApi } from '../hooks'
import { useAuth } from '../auth'
import { PageHeader, Card, Button, Field, Modal, Spinner, ErrorBanner, EmptyState, Pagination, Badge } from '../components/ui'

const PERIODS = ['daily', 'weekly', 'monthly', 'yearly']

const EMPTY = {
  name: '',
  price: '',
  billing_period: 'monthly',
  min_quantity: 1,
  start_date: '',
  end_date: '',
  auto_close_on_end: false,
  allow_early_close: true,
  allow_pause: true,
  allow_renew: true,
}

const FLAGS = [
  ['auto_close_on_end', 'Auto-close on end'],
  ['allow_early_close', 'Allow early close'],
  ['allow_pause', 'Allow pause'],
  ['allow_renew', 'Allow renew'],
]

export default function Plans() {
  const { isAdmin } = useAuth()
  const [page, setPage] = useState(1)
  const [modal, setModal] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const plans = useApi('/plans', { page, page_size: 20 })

  function openCreate() {
    setEditing(null)
    setForm(EMPTY)
    setError('')
    setModal(true)
  }

  function openEdit(plan) {
    setEditing(plan)
    setForm({
      name: plan.name,
      price: String(plan.price),
      billing_period: plan.billing_period,
      min_quantity: plan.min_quantity,
      start_date: plan.start_date || '',
      end_date: plan.end_date || '',
      auto_close_on_end: plan.auto_close_on_end,
      allow_early_close: plan.allow_early_close,
      allow_pause: plan.allow_pause,
      allow_renew: plan.allow_renew,
    })
    setError('')
    setModal(true)
  }

  async function save(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    const payload = {
      ...form,
      price: Number(form.price || 0),
      min_quantity: Number(form.min_quantity || 1),
      start_date: form.start_date || null,
      end_date: form.end_date || null,
    }
    try {
      if (editing) await api(`/plans/${editing.id}`, { method: 'PUT', body: payload })
      else await api('/plans', { method: 'POST', body: payload })
      setModal(false)
      plans.reload()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Plans"
        subtitle="Billing cadence, minimum quantity and lifecycle rules per plan."
        actions={isAdmin && <Button onClick={openCreate}>New plan</Button>}
      />
      <Card>
        <ErrorBanner message={plans.error} onRetry={plans.reload} />
        {plans.loading && !plans.data ? (
          <Spinner />
        ) : !plans.data?.items?.length ? (
          <EmptyState title="No plans yet" hint="Create a plan to start selling subscriptions." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Plan</th>
                  <th>Billing</th>
                  <th className="num">Price</th>
                  <th className="num">Min qty</th>
                  <th>Availability</th>
                  <th>Rules</th>
                  {isAdmin && <th />}
                </tr>
              </thead>
              <tbody>
                {plans.data.items.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <strong>{p.name}</strong>
                      {!p.is_active && <div className="muted small">Inactive</div>}
                    </td>
                    <td><Badge status="quotation">{p.billing_period}</Badge></td>
                    <td className="num">{formatMoney(p.price)}</td>
                    <td className="num">{p.min_quantity}</td>
                    <td className="small">
                      {p.start_date || p.end_date
                        ? `${p.start_date ? formatDate(p.start_date) : 'Anytime'} → ${p.end_date ? formatDate(p.end_date) : 'Open'}`
                        : 'Always available'}
                    </td>
                    <td>
                      <div className="chip-list">
                        {p.auto_close_on_end && <span className="chip">auto-close</span>}
                        {p.allow_early_close && <span className="chip">early close</span>}
                        {p.allow_pause && <span className="chip">pause</span>}
                        {p.allow_renew && <span className="chip">renew</span>}
                        {!p.auto_close_on_end && !p.allow_early_close && !p.allow_pause && !p.allow_renew && (
                          <span className="muted small">Locked</span>
                        )}
                      </div>
                    </td>
                    {isAdmin && (
                      <td className="right">
                        <Button size="sm" variant="ghost" onClick={() => openEdit(p)}>Edit</Button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pagination page={page} pageSize={20} total={plans.data?.total || 0} onPage={setPage} />
      </Card>

      <Modal
        open={modal}
        onClose={() => setModal(false)}
        title={editing ? `Edit ${editing.name}` : 'New plan'}
        wide
        footer={
          <>
            <Button variant="ghost" onClick={() => setModal(false)}>Cancel</Button>
            <Button onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save plan'}</Button>
          </>
        }
      >
        <form onSubmit={save} className="form-stack">
          <ErrorBanner message={error} />
          <div className="grid-2">
            <Field label="Plan name">
              <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            </Field>
            <Field label="Price">
              <input className="input" type="number" min="0" step="0.01" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} required />
            </Field>
            <Field label="Billing period">
              <select className="input" value={form.billing_period} onChange={(e) => setForm({ ...form, billing_period: e.target.value })}>
                {PERIODS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </Field>
            <Field label="Minimum quantity">
              <input className="input" type="number" min="1" value={form.min_quantity} onChange={(e) => setForm({ ...form, min_quantity: e.target.value })} />
            </Field>
            <Field label="Available from">
              <input className="input" type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
            </Field>
            <Field label="Available until">
              <input className="input" type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} />
            </Field>
          </div>
          <Field label="Plan rules">
            <div className="check-grid">
              {FLAGS.map(([key, label]) => (
                <label className="check" key={key}>
                  <input type="checkbox" checked={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.checked })} />
                  {label}
                </label>
              ))}
            </div>
          </Field>
        </form>
      </Modal>
    </>
  )
}
