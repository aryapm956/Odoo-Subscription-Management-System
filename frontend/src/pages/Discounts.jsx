import { useState } from 'react'
import { api, formatMoney, formatDate, todayISO } from '../api'
import { useApi } from '../hooks'
import { useAuth } from '../auth'
import { PageHeader, Card, Button, Field, Modal, Spinner, ErrorBanner, EmptyState, Pagination, Badge } from '../components/ui'

const EMPTY = {
  name: '',
  type: 'percentage',
  value: '',
  min_purchase: '',
  min_quantity: '',
  start_date: '',
  end_date: '',
  usage_limit: '',
  applies_to: 'subscription',
  product_id: '',
  subscription_id: '',
  plan_id: '',
}

function discountState(d) {
  const today = todayISO()
  if (d.end_date && d.end_date < today) return { status: 'expired', label: 'Expired' }
  if (d.usage_limit != null && d.times_used >= d.usage_limit) return { status: 'exhausted', label: 'Limit reached' }
  if (d.start_date && d.start_date > today) return { status: 'scheduled', label: 'Scheduled' }
  return { status: 'active', label: 'Active' }
}

export default function Discounts() {
  const { isAdmin } = useAuth()
  const [page, setPage] = useState(1)
  const [modal, setModal] = useState(false)
  const [form, setForm] = useState(EMPTY)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const discounts = useApi('/discounts', { page, page_size: 20 })
  const products = useApi('/products', { page_size: 200 })
  const subscriptions = useApi('/subscriptions', { page_size: 100 })
  const plans = useApi('/plans', { page_size: 100 })

  async function save(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api('/discounts', {
        method: 'POST',
        body: {
          name: form.name,
          type: form.type,
          value: Number(form.value || 0),
          min_purchase: form.min_purchase ? Number(form.min_purchase) : null,
          min_quantity: form.min_quantity ? Number(form.min_quantity) : null,
          start_date: form.start_date || null,
          end_date: form.end_date || null,
          usage_limit: form.usage_limit ? Number(form.usage_limit) : null,
          applies_to: form.applies_to,
          product_id: form.applies_to === 'product' && form.product_id ? Number(form.product_id) : null,
          subscription_id: form.applies_to === 'subscription' && form.subscription_id ? Number(form.subscription_id) : null,
          plan_id: form.plan_id ? Number(form.plan_id) : null,
        },
      })
      setModal(false)
      setForm(EMPTY)
      discounts.reload()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Discounts"
        subtitle="Admin-controlled rules that auto-apply to the next invoice."
        actions={isAdmin && <Button onClick={() => setModal(true)}>New discount</Button>}
      />
      <Card>
        <ErrorBanner message={discounts.error || error} onRetry={discounts.reload} />
        {discounts.loading && !discounts.data ? (
          <Spinner />
        ) : !discounts.data?.items?.length ? (
          <EmptyState title="No discount rules" hint="Create a percentage or fixed discount with limits and dates." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Rule</th>
                  <th>Value</th>
                  <th>Applies to</th>
                  <th>Conditions</th>
                  <th>Window</th>
                  <th>Usage</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {discounts.data.items.map((d) => {
                  const state = discountState(d)
                  const product = products.data?.items?.find((p) => p.id === d.product_id)
                  const plan = plans.data?.items?.find((p) => p.id === d.plan_id)
                  return (
                    <tr key={d.id}>
                      <td><strong>{d.name}</strong></td>
                      <td>{d.type === 'percentage' ? `${d.value}%` : formatMoney(d.value)}</td>
                      <td>
                        {d.applies_to === 'product'
                          ? `Product · ${product?.name || d.product_id}`
                          : d.subscription_id
                            ? `Subscription #${d.subscription_id}`
                            : 'Whole subscription'}
                        {plan ? ` · ${plan.name} only` : ''}
                      </td>
                      <td className="small">
                        {d.min_purchase ? `Min purchase ${formatMoney(d.min_purchase)}` : 'No min purchase'}
                        {d.min_quantity ? ` · Min qty ${d.min_quantity}` : ''}
                      </td>
                      <td className="small">
                        {d.start_date || d.end_date
                          ? `${d.start_date ? formatDate(d.start_date) : 'Anytime'} → ${d.end_date ? formatDate(d.end_date) : 'Open'}`
                          : 'Always'}
                      </td>
                      <td className="small">
                        {d.times_used} used{d.usage_limit != null ? ` / ${d.usage_limit}` : ''}
                      </td>
                      <td><Badge status={state.status}>{state.label}</Badge></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        <Pagination page={page} pageSize={20} total={discounts.data?.total || 0} onPage={setPage} />
      </Card>

      <Modal
        open={modal}
        onClose={() => setModal(false)}
        title="New discount rule"
        wide
        footer={
          <>
            <Button variant="ghost" onClick={() => setModal(false)}>Cancel</Button>
            <Button onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save discount'}</Button>
          </>
        }
      >
        <form onSubmit={save} className="form-stack">
          <ErrorBanner message={error} />
          <div className="grid-2">
            <Field label="Rule name">
              <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            </Field>
            <Field label="Type">
              <select className="input" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
                <option value="percentage">Percentage</option>
                <option value="fixed">Fixed amount</option>
              </select>
            </Field>
            <Field label={form.type === 'percentage' ? 'Value (%)' : 'Value (amount)'}>
              <input className="input" type="number" min="0" step="0.01" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} required />
            </Field>
            <Field label="Applies to">
              <select className="input" value={form.applies_to} onChange={(e) => setForm({ ...form, applies_to: e.target.value })}>
                <option value="subscription">Whole subscription</option>
                <option value="product">Specific product</option>
              </select>
            </Field>
            <Field label="Limit to one plan" hint="Leave blank to apply to every plan.">
              <select className="input" value={form.plan_id} onChange={(e) => setForm({ ...form, plan_id: e.target.value })}>
                <option value="">All plans</option>
                {(plans.data?.items || []).map((p) => (
                  <option key={p.id} value={p.id}>{p.name} · {p.billing_period}</option>
                ))}
              </select>
            </Field>
            {form.applies_to === 'product' && (
              <Field label="Product">
                <select className="input" value={form.product_id} onChange={(e) => setForm({ ...form, product_id: e.target.value })} required>
                  <option value="">Select product</option>
                  {(products.data?.items || []).map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </Field>
            )}
            {form.applies_to === 'subscription' && (
              <Field label="Limit to one subscription" hint="Leave blank to apply to every subscription.">
                <select className="input" value={form.subscription_id} onChange={(e) => setForm({ ...form, subscription_id: e.target.value })}>
                  <option value="">All subscriptions</option>
                  {(subscriptions.data?.items || []).map((s) => (
                    <option key={s.id} value={s.id}>{s.number} · {s.customer_name}</option>
                  ))}
                </select>
              </Field>
            )}
            <Field label="Minimum purchase">
              <input className="input" type="number" min="0" step="0.01" value={form.min_purchase} onChange={(e) => setForm({ ...form, min_purchase: e.target.value })} />
            </Field>
            <Field label="Minimum quantity">
              <input className="input" type="number" min="0" value={form.min_quantity} onChange={(e) => setForm({ ...form, min_quantity: e.target.value })} />
            </Field>
            <Field label="Start date">
              <input className="input" type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
            </Field>
            <Field label="End date">
              <input className="input" type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} />
            </Field>
            <Field label="Usage limit">
              <input className="input" type="number" min="1" value={form.usage_limit} onChange={(e) => setForm({ ...form, usage_limit: e.target.value })} placeholder="Unlimited" />
            </Field>
          </div>
        </form>
      </Modal>
    </>
  )
}
