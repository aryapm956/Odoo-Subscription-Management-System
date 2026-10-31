import { useState } from 'react'
import { api, formatDate, formatMoney, todayISO, addDaysISO } from '../api'
import { useApi } from '../hooks'
import { useAuth } from '../auth'
import { PageHeader, Card, Button, Field, Modal, Spinner, ErrorBanner, EmptyState, Pagination, Badge, SuccessBanner } from '../components/ui'

const PAYMENT_TERMS = ['Immediate', 'Net 15', 'Net 30', 'Net 60']

const EMPTY_LINE = { product_id: '', variant_id: '', quantity: 1, unit_price: '', tax_id: '' }

function emptyForm() {
  return {
    customer_id: '',
    plan_id: '',
    start_date: todayISO(),
    expiry_date: addDaysISO(365),
    payment_terms: 'Immediate',
    notes: '',
    from_template_id: '',
    lines: [{ ...EMPTY_LINE }],
  }
}

export default function Subscriptions({ navigate, portal = false }) {
  const { isStaff } = useAuth()
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const [modal, setModal] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [billing, setBilling] = useState(null)

  const subs = useApi('/subscriptions', { page, page_size: 20, status: status || undefined, search: search || undefined })
  const customers = useApi(isStaff && modal ? '/customers' : null, { page_size: 200 })
  const plans = useApi(isStaff && modal ? '/plans' : null, { page_size: 200 })
  const products = useApi(isStaff && modal ? '/products' : null, { page_size: 200 })
  const taxes = useApi(isStaff && modal ? '/taxes' : null)
  const templates = useApi(isStaff && modal ? '/templates' : null)

  const defaultTax = taxes.data?.find((t) => t.is_default)

  function openCreate() {
    setForm(emptyForm())
    setError('')
    setModal(true)
  }

  function productFor(id) {
    return products.data?.items?.find((p) => p.id === Number(id))
  }

  function updateLine(index, key, value) {
    setForm((prev) => ({
      ...prev,
      lines: prev.lines.map((line, i) => {
        if (i !== index) return line
        if (key === 'product_id') {
          const product = productFor(value)
          const taxId = product?.tax_ids?.[0] || defaultTax?.id || ''
          return { ...line, product_id: value, variant_id: '', unit_price: product ? product.sales_price : '', tax_id: taxId }
        }
        if (key === 'variant_id') {
          const product = productFor(line.product_id)
          const variant = product?.variants?.find((v) => v.id === Number(value))
          const price = product ? Number(product.sales_price) + Number(variant?.extra_price || 0) : ''
          return { ...line, variant_id: value, unit_price: price }
        }
        return { ...line, [key]: value }
      }),
    }))
  }

  function applyTemplate(templateId) {
    const template = templates.data?.find((t) => t.id === Number(templateId))
    if (!template) {
      setForm((prev) => ({ ...prev, from_template_id: '', lines: [{ ...EMPTY_LINE }] }))
      return
    }
    const lines = template.lines.map((line) => {
      const product = productFor(line.product_id)
      const variant = product?.variants?.find((v) => v.id === line.variant_id)
      return {
        product_id: String(line.product_id),
        variant_id: line.variant_id ? String(line.variant_id) : '',
        quantity: line.quantity,
        unit_price: product ? Number(product.sales_price) + Number(variant?.extra_price || 0) : '',
        tax_id: product?.tax_ids?.[0] || defaultTax?.id || '',
      }
    })
    setForm((prev) => ({
      ...prev,
      from_template_id: String(templateId),
      plan_id: template.plan_id ? String(template.plan_id) : prev.plan_id,
      lines: lines.length ? lines : [{ ...EMPTY_LINE }],
    }))
  }

  async function save(e) {
    e.preventDefault()
    setError('')
    const lines = form.lines.filter((line) => line.product_id)
    if (!lines.length) {
      setError('Add at least one product line.')
      return
    }
    setBusy(true)
    try {
      const created = await api('/subscriptions', {
        method: 'POST',
        body: {
          customer_id: Number(form.customer_id),
          plan_id: Number(form.plan_id),
          start_date: form.start_date,
          expiry_date: form.expiry_date || null,
          payment_terms: form.payment_terms,
          notes: form.notes || null,
          from_template_id: form.from_template_id ? Number(form.from_template_id) : null,
          lines: lines.map((line) => ({
            product_id: Number(line.product_id),
            variant_id: line.variant_id ? Number(line.variant_id) : null,
            quantity: Number(line.quantity || 1),
            unit_price: Number(line.unit_price || 0),
            tax_id: line.tax_id ? Number(line.tax_id) : null,
          })),
        },
      })
      setModal(false)
      subs.reload()
      if (created?.id) navigate(`/subscriptions/${created.id}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function runBilling() {
    setBilling(null)
    setError('')
    try {
      const result = await api('/invoices/billing-run', { method: 'POST' })
      setBilling(`Billing run complete: ${result.created} created, ${result.skipped} skipped, ${result.failed} failed, ${result.closed} closed.`)
      subs.reload()
    } catch (err) {
      setError(err.message)
    }
  }

  const title = portal ? 'My subscriptions' : 'Subscriptions'
  const subtitle = portal
    ? 'Your plans, renewal dates and billing status.'
    : 'Every subscription from draft to closed, with the next billing date.'

  return (
    <>
      <PageHeader
        title={title}
        subtitle={subtitle}
        actions={
          isStaff && !portal ? (
            <>
              <Button variant="ghost" onClick={runBilling}>Run billing</Button>
              <Button onClick={openCreate}>New subscription</Button>
            </>
          ) : null
        }
      />
      {billing && <SuccessBanner message={billing} />}
      <Card>
        <div className="toolbar">
          <input
            className="input search"
            placeholder="Search by subscription number…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(1)
            }}
          />
          <select
            className="input compact"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value)
              setPage(1)
            }}
          >
            <option value="">All statuses</option>
            {['draft', 'quotation', 'confirmed', 'active', 'closed'].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <span className="muted small">{subs.data?.total ?? 0} subscriptions</span>
        </div>
        <ErrorBanner message={subs.error || error} onRetry={subs.reload} />
        {subs.loading && !subs.data ? (
          <Spinner />
        ) : !subs.data?.items?.length ? (
          <EmptyState title="No subscriptions found" hint={portal ? 'Contact Brightloop to start a subscription.' : 'Create a subscription from scratch or a template.'} />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Number</th>
                  {!portal && <th>Customer</th>}
                  <th>Plan</th>
                  <th>Term</th>
                  <th>Next billing</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {subs.data.items.map((sub) => (
                  <tr key={sub.id} className="clickable" onClick={() => navigate(`${portal ? '/portal' : ''}/subscriptions/${sub.id}`)}>
                    <td><strong>{sub.number}</strong></td>
                    {!portal && <td>{sub.customer_name}</td>}
                    <td>
                      <div>{sub.plan_name}</div>
                      <div className="muted small">{sub.billing_period}</div>
                    </td>
                    <td className="small">
                      {formatDate(sub.start_date)}
                      <div className="muted">to {formatDate(sub.expiry_date)}</div>
                    </td>
                    <td className="small">{sub.paused ? <Badge status="closed">Paused</Badge> : formatDate(sub.next_billing_date)}</td>
                    <td><Badge status={sub.status}>{sub.status}</Badge></td>
                    <td className="right">
                      <Button size="sm" variant="ghost" onClick={(e) => { e.stopPropagation(); navigate(`${portal ? '/portal' : ''}/subscriptions/${sub.id}`) }}>
                        View
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pagination page={page} pageSize={20} total={subs.data?.total || 0} onPage={setPage} />
      </Card>

      {isStaff && !portal && (
        <Modal
          open={modal}
          onClose={() => setModal(false)}
          title="New subscription"
          wide
          footer={
            <>
              <Button variant="ghost" onClick={() => setModal(false)}>Cancel</Button>
              <Button onClick={save} loading={busy}>{busy ? 'Creating…' : 'Create subscription'}</Button>
            </>
          }
        >
          <form onSubmit={save} className="form-stack">
            <ErrorBanner message={error} />
            <div className="grid-2">
              <Field label="Customer">
                <select className="input" value={form.customer_id} onChange={(e) => setForm({ ...form, customer_id: e.target.value })} required>
                  <option value="">Select customer</option>
                  {(customers.data?.items || []).map((c) => (
                    <option key={c.id} value={c.id}>{c.name}{c.company ? ` · ${c.company}` : ''}</option>
                  ))}
                </select>
              </Field>
              <Field label="Plan">
                <select className="input" value={form.plan_id} onChange={(e) => setForm({ ...form, plan_id: e.target.value })} required>
                  <option value="">Select plan</option>
                  {(plans.data?.items || []).map((p) => (
                    <option key={p.id} value={p.id}>{p.name} · {p.billing_period} · {formatMoney(p.price)}</option>
                  ))}
                </select>
              </Field>
              <Field label="Start from template" hint="Optional — loads the template's plan and product lines.">
                <select className="input" value={form.from_template_id} onChange={(e) => applyTemplate(e.target.value)}>
                  <option value="">From scratch</option>
                  {(templates.data || []).map((t) => (
                    <option key={t.id} value={t.id}>{t.name} · valid {t.validity_days} days</option>
                  ))}
                </select>
              </Field>
              <Field label="Payment terms">
                <select className="input" value={form.payment_terms} onChange={(e) => setForm({ ...form, payment_terms: e.target.value })}>
                  {PAYMENT_TERMS.map((term) => <option key={term} value={term}>{term}</option>)}
                </select>
              </Field>
              <Field label="Start date">
                <input className="input" type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} required />
              </Field>
              <Field label="Expiry date">
                <input className="input" type="date" value={form.expiry_date} onChange={(e) => setForm({ ...form, expiry_date: e.target.value })} />
              </Field>
            </div>
            <Field label="Notes">
              <textarea className="input" rows="2" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </Field>

            <Field label="Subscription lines">
              <div className="line-editor">
                {form.lines.map((line, index) => {
                  const product = productFor(line.product_id)
                  return (
                    <div className="line-row subscription-line" key={index}>
                      <select className="input" value={line.product_id} onChange={(e) => updateLine(index, 'product_id', e.target.value)}>
                        <option value="">Select product</option>
                        {(products.data?.items || []).map((p) => (
                          <option key={p.id} value={p.id}>{p.name}</option>
                        ))}
                      </select>
                      <select className="input" value={line.variant_id} onChange={(e) => updateLine(index, 'variant_id', e.target.value)} disabled={!product?.variants?.length}>
                        <option value="">No variant</option>
                        {(product?.variants || []).map((v) => (
                          <option key={v.id} value={v.id}>{v.attribute}: {v.value} {v.extra_price ? `+${formatMoney(v.extra_price)}` : ''}</option>
                        ))}
                      </select>
                      <input className="input qty" type="number" min="1" value={line.quantity} onChange={(e) => updateLine(index, 'quantity', e.target.value)} />
                      <input className="input price" type="number" min="0" step="0.01" value={line.unit_price} onChange={(e) => updateLine(index, 'unit_price', e.target.value)} placeholder="Unit price" />
                      <select className="input" value={line.tax_id} onChange={(e) => updateLine(index, 'tax_id', e.target.value)}>
                        <option value="">Default tax</option>
                        {(taxes.data || []).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                      </select>
                      <Button size="sm" variant="ghost" onClick={() => setForm((prev) => ({ ...prev, lines: prev.lines.filter((_, i) => i !== index) }))}>
                        Remove
                      </Button>
                    </div>
                  )
                })}
                <Button size="sm" variant="ghost" onClick={() => setForm((prev) => ({ ...prev, lines: [...prev.lines, { ...EMPTY_LINE }] }))}>
                  + Add line
                </Button>
              </div>
            </Field>
          </form>
        </Modal>
      )}
    </>
  )
}
