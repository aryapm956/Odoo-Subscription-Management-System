import { useState } from 'react'
import { api, formatMoney } from '../api'
import { useApi } from '../hooks'
import { useAuth } from '../auth'
import { PageHeader, Card, Button, Field, Modal, Spinner, ErrorBanner, EmptyState, Pagination, Badge } from '../components/ui'

const PRODUCT_TYPES = ['software', 'service', 'goods', 'addon']

const EMPTY_FORM = {
  name: '',
  type: 'software',
  sales_price: '',
  cost_price: '',
  notes: '',
  tax_ids: [],
  variants: [],
}

function variantRow() {
  return { attribute: 'Brand', value: '', extra_price: '' }
}

export default function Products() {
  const { isAdmin } = useAuth()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [modal, setModal] = useState(null)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [newVariants, setNewVariants] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const products = useApi('/products', { page, page_size: 20, search: search || undefined })
  const taxes = useApi('/taxes')

  function openCreate() {
    setEditing(null)
    setForm(EMPTY_FORM)
    setNewVariants([variantRow()])
    setError('')
    setModal('create')
  }

  function openEdit(product) {
    setEditing(product)
    setForm({
      name: product.name,
      type: product.type,
      sales_price: String(product.sales_price),
      cost_price: String(product.cost_price),
      notes: product.notes || '',
      tax_ids: product.tax_ids || [],
      variants: [],
    })
    setNewVariants([])
    setError('')
    setModal('edit')
  }

  function setField(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  function toggleTax(id) {
    setForm((prev) => ({
      ...prev,
      tax_ids: prev.tax_ids.includes(id) ? prev.tax_ids.filter((t) => t !== id) : [...prev.tax_ids, id],
    }))
  }

  function updateVariant(index, key, value) {
    setNewVariants((rows) => rows.map((row, i) => (i === index ? { ...row, [key]: value } : row)))
  }

  async function save(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const payload = {
        name: form.name,
        type: form.type,
        sales_price: Number(form.sales_price || 0),
        cost_price: Number(form.cost_price || 0),
        notes: form.notes || null,
        tax_ids: form.tax_ids,
      }
      if (modal === 'create') {
        await api('/products', {
          method: 'POST',
          body: {
            ...payload,
            variants: newVariants
              .filter((v) => v.value.trim())
              .map((v) => ({ attribute: v.attribute, value: v.value, extra_price: Number(v.extra_price || 0) })),
          },
        })
      } else {
        await api(`/products/${editing.id}`, { method: 'PUT', body: payload })
        for (const v of newVariants.filter((row) => row.value.trim())) {
          await api(`/products/${editing.id}/variants`, {
            method: 'POST',
            body: { attribute: v.attribute, value: v.value, extra_price: Number(v.extra_price || 0) },
          })
        }
      }
      setModal(null)
      products.reload()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function removeVariant(variantId) {
    try {
      await api(`/products/${editing.id}/variants/${variantId}`, { method: 'DELETE' })
      const fresh = await api(`/products/${editing.id}`)
      setEditing(fresh)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <>
      <PageHeader
        title="Products"
        subtitle="Products, variants and the taxes that follow them."
        actions={isAdmin && <Button onClick={openCreate}>New product</Button>}
      />
      <Card>
        <div className="toolbar">
          <input
            className="input search"
            placeholder="Search products…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(1)
            }}
          />
          <span className="muted small">{products.data?.total ?? 0} products</span>
        </div>
        <ErrorBanner message={products.error} onRetry={products.reload} />
        {products.loading && !products.data ? (
          <Spinner />
        ) : !products.data?.items?.length ? (
          <EmptyState title="No products yet" hint="Admin users can add products and variants." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Type</th>
                  <th className="num">Sales price</th>
                  <th className="num">Cost price</th>
                  <th>Variants</th>
                  <th>Taxes</th>
                  {isAdmin && <th />}
                </tr>
              </thead>
              <tbody>
                {products.data.items.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <strong>{p.name}</strong>
                      {p.notes && <div className="muted small">{p.notes}</div>}
                    </td>
                    <td><Badge status="quotation">{p.type}</Badge></td>
                    <td className="num">{formatMoney(p.sales_price)}</td>
                    <td className="num">{formatMoney(p.cost_price)}</td>
                    <td>
                      {p.variants.length === 0 ? (
                        <span className="muted small">None</span>
                      ) : (
                        <div className="chip-list">
                          {p.variants.map((v) => (
                            <span className="chip" key={v.id}>
                              {v.attribute}: {v.value} {v.extra_price ? `+${formatMoney(v.extra_price)}` : ''}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td>
                      <div className="chip-list">
                        {(p.tax_ids || []).map((id) => {
                          const tax = taxes.data?.find((t) => t.id === id)
                          return tax ? <span className="chip" key={id}>{tax.name}</span> : null
                        })}
                        {!p.tax_ids?.length && <span className="muted small">Default</span>}
                      </div>
                    </td>
                    {isAdmin && (
                      <td className="right">
                        <Button size="sm" variant="ghost" onClick={() => openEdit(p)}>
                          Edit
                        </Button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pagination page={page} pageSize={20} total={products.data?.total || 0} onPage={setPage} />
      </Card>

      <Modal
        open={Boolean(modal)}
        onClose={() => setModal(null)}
        title={modal === 'edit' ? `Edit ${editing?.name}` : 'New product'}
        wide
        footer={
          <>
            <Button variant="ghost" onClick={() => setModal(null)}>Cancel</Button>
            <Button onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save product'}</Button>
          </>
        }
      >
        <form onSubmit={save} className="form-stack">
          <ErrorBanner message={error} />
          <div className="grid-2">
            <Field label="Name">
              <input className="input" value={form.name} onChange={(e) => setField('name', e.target.value)} required />
            </Field>
            <Field label="Type">
              <select className="input" value={form.type} onChange={(e) => setField('type', e.target.value)}>
                {PRODUCT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </Field>
            <Field label="Sales price">
              <input className="input" type="number" min="0" step="0.01" value={form.sales_price} onChange={(e) => setField('sales_price', e.target.value)} />
            </Field>
            <Field label="Cost price">
              <input className="input" type="number" min="0" step="0.01" value={form.cost_price} onChange={(e) => setField('cost_price', e.target.value)} />
            </Field>
          </div>
          <Field label="Notes">
            <textarea className="input" rows="2" value={form.notes} onChange={(e) => setField('notes', e.target.value)} />
          </Field>
          <Field label="Taxes" hint="A default tax is applied automatically if no tax is selected.">
            <div className="check-grid">
              {(taxes.data || []).map((t) => (
                <label className="check" key={t.id}>
                  <input type="checkbox" checked={form.tax_ids.includes(t.id)} onChange={() => toggleTax(t.id)} />
                  {t.name} ({t.rate_percent}%)
                </label>
              ))}
            </div>
          </Field>

          {editing?.variants?.length > 0 && (
            <Field label="Existing variants">
              <div className="chip-list">
                {editing.variants.map((v) => (
                  <span className="chip" key={v.id}>
                    {v.attribute}: {v.value} {v.extra_price ? `+${formatMoney(v.extra_price)}` : ''}
                    <button type="button" className="chip-x" onClick={() => removeVariant(v.id)}>×</button>
                  </span>
                ))}
              </div>
            </Field>
          )}

          <Field label="Add variants" hint="Example: Brand = Odoo with an extra price of 560.">
            <div className="variant-list">
              {newVariants.map((row, index) => (
                <div className="variant-row" key={index}>
                  <input className="input" placeholder="Attribute" value={row.attribute} onChange={(e) => updateVariant(index, 'attribute', e.target.value)} />
                  <input className="input" placeholder="Value" value={row.value} onChange={(e) => updateVariant(index, 'value', e.target.value)} />
                  <input className="input" type="number" step="0.01" placeholder="Extra price" value={row.extra_price} onChange={(e) => updateVariant(index, 'extra_price', e.target.value)} />
                  <Button size="sm" variant="ghost" onClick={() => setNewVariants((rows) => rows.filter((_, i) => i !== index))}>
                    Remove
                  </Button>
                </div>
              ))}
              <Button size="sm" variant="ghost" onClick={() => setNewVariants((rows) => [...rows, variantRow()])}>
                + Add variant
              </Button>
            </div>
          </Field>
        </form>
      </Modal>
    </>
  )
}
