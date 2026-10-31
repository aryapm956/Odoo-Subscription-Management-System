import { useState } from 'react'
import { api } from '../api'
import { useApi } from '../hooks'
import { useAuth } from '../auth'
import { PageHeader, Card, Button, Field, Modal, Spinner, ErrorBanner, EmptyState, Badge } from '../components/ui'

const EMPTY_LINE = { product_id: '', variant_id: '', quantity: 1 }

export default function Templates() {
  const { isAdmin } = useAuth()
  const [modal, setModal] = useState(false)
  const [form, setForm] = useState({ name: '', validity_days: 30, plan_id: '', lines: [EMPTY_LINE] })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const templates = useApi('/templates')
  const products = useApi('/products', { page_size: 200 })
  const plans = useApi('/plans', { page_size: 200 })

  function productFor(id) {
    return products.data?.items?.find((p) => p.id === Number(id))
  }

  function updateLine(index, key, value) {
    setForm((prev) => ({
      ...prev,
      lines: prev.lines.map((line, i) => {
        if (i !== index) return line
        if (key === 'product_id') return { ...line, product_id: value, variant_id: '' }
        return { ...line, [key]: value }
      }),
    }))
  }

  async function save(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api('/templates', {
        method: 'POST',
        body: {
          name: form.name,
          validity_days: Number(form.validity_days || 30),
          plan_id: form.plan_id ? Number(form.plan_id) : null,
          lines: form.lines
            .filter((line) => line.product_id)
            .map((line) => ({
              product_id: Number(line.product_id),
              variant_id: line.variant_id ? Number(line.variant_id) : null,
              quantity: Number(line.quantity || 1),
            })),
        },
      })
      setModal(false)
      setForm({ name: '', validity_days: 30, plan_id: '', lines: [EMPTY_LINE] })
      templates.reload()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function remove(template) {
    if (!window.confirm(`Delete template “${template.name}”?`)) return
    try {
      await api(`/templates/${template.id}`, { method: 'DELETE' })
      templates.reload()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <>
      <PageHeader
        title="Quotation templates"
        subtitle="Reusable plan + product bundles with a validity window."
        actions={isAdmin && <Button onClick={() => setModal(true)}>New template</Button>}
      />
      <Card>
        <ErrorBanner message={templates.error || error} onRetry={templates.reload} />
        {templates.loading && !templates.data ? (
          <Spinner />
        ) : !templates.data?.length ? (
          <EmptyState title="No templates yet" hint="Bundle a plan and product lines for faster quotes." />
        ) : (
          <div className="template-grid">
            {templates.data.map((template) => (
              <div className="template-card" key={template.id}>
                <div className="row-between">
                  <strong>{template.name}</strong>
                  {isAdmin && (
                    <Button size="sm" variant="ghost" onClick={() => remove(template)}>Delete</Button>
                  )}
                </div>
                <div className="template-meta">
                  <Badge status="quotation">{template.plan_name || 'No plan'}</Badge>
                  <span className="muted small">Valid for {template.validity_days} days</span>
                </div>
                <ul className="line-list">
                  {template.lines.map((line) => (
                    <li key={line.id}>
                      <span>{line.product_name}</span>
                      <span className="muted">× {line.quantity}</span>
                    </li>
                  ))}
                  {!template.lines.length && <li className="muted small">No product lines</li>}
                </ul>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Modal
        open={modal}
        onClose={() => setModal(false)}
        title="New quotation template"
        wide
        footer={
          <>
            <Button variant="ghost" onClick={() => setModal(false)}>Cancel</Button>
            <Button onClick={save} loading={busy}>{busy ? 'Saving…' : 'Save template'}</Button>
          </>
        }
      >
        <form onSubmit={save} className="form-stack">
          <ErrorBanner message={error} />
          <div className="grid-2">
            <Field label="Template name">
              <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            </Field>
            <Field label="Validity (days)">
              <input className="input" type="number" min="1" value={form.validity_days} onChange={(e) => setForm({ ...form, validity_days: e.target.value })} />
            </Field>
            <Field label="Plan">
              <select className="input" value={form.plan_id} onChange={(e) => setForm({ ...form, plan_id: e.target.value })}>
                <option value="">No plan</option>
                {(plans.data?.items || []).map((plan) => (
                  <option key={plan.id} value={plan.id}>{plan.name} · {plan.billing_period}</option>
                ))}
              </select>
            </Field>
          </div>

          <Field label="Product lines">
            <div className="line-editor">
              {form.lines.map((line, index) => {
                const product = productFor(line.product_id)
                return (
                  <div className="line-row" key={index}>
                    <select className="input" value={line.product_id} onChange={(e) => updateLine(index, 'product_id', e.target.value)}>
                      <option value="">Select product</option>
                      {(products.data?.items || []).map((p) => (
                        <option key={p.id} value={p.id}>{p.name}</option>
                      ))}
                    </select>
                    <select className="input" value={line.variant_id} onChange={(e) => updateLine(index, 'variant_id', e.target.value)} disabled={!product?.variants?.length}>
                      <option value="">No variant</option>
                      {(product?.variants || []).map((v) => (
                        <option key={v.id} value={v.id}>{v.attribute}: {v.value}</option>
                      ))}
                    </select>
                    <input className="input" type="number" min="1" value={line.quantity} onChange={(e) => updateLine(index, 'quantity', e.target.value)} />
                    <Button size="sm" variant="ghost" onClick={() => setForm((prev) => ({ ...prev, lines: prev.lines.filter((_, i) => i !== index) }))}>
                      Remove
                    </Button>
                  </div>
                )
              })}
              <Button size="sm" variant="ghost" onClick={() => setForm((prev) => ({ ...prev, lines: [...prev.lines, EMPTY_LINE] }))}>
                + Add line
              </Button>
            </div>
          </Field>
        </form>
      </Modal>
    </>
  )
}
