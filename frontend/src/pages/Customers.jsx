import { useState } from 'react'
import { api } from '../api'
import { useApi } from '../hooks'
import { PageHeader, Card, Button, Field, Modal, Spinner, ErrorBanner, EmptyState, Pagination } from '../components/ui'

const EMPTY = { name: '', email: '', phone: '', company: '', address: '' }

export default function Customers() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [modal, setModal] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const customers = useApi('/customers', { page, page_size: 20, search: search || undefined })

  function openCreate() {
    setEditing(null)
    setForm(EMPTY)
    setError('')
    setModal(true)
  }

  function openEdit(customer) {
    setEditing(customer)
    setForm({
      name: customer.name,
      email: customer.email,
      phone: customer.phone || '',
      company: customer.company || '',
      address: customer.address || '',
    })
    setError('')
    setModal(true)
  }

  async function save(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      if (editing) await api(`/customers/${editing.id}`, { method: 'PUT', body: form })
      else await api('/customers', { method: 'POST', body: form })
      setModal(false)
      customers.reload()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Customers"
        subtitle="People and companies that hold subscriptions with Brightloop."
        actions={<Button onClick={openCreate}>New customer</Button>}
      />
      <Card>
        <div className="toolbar">
          <input
            className="input search"
            placeholder="Search name, email or company…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(1)
            }}
          />
          <span className="muted small">{customers.data?.total ?? 0} customers</span>
        </div>
        <ErrorBanner message={customers.error || error} onRetry={customers.reload} />
        {customers.loading && !customers.data ? (
          <Spinner />
        ) : !customers.data?.items?.length ? (
          <EmptyState title="No customers yet" hint="Add your first customer to create a subscription." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Customer</th>
                  <th>Company</th>
                  <th>Contact</th>
                  <th>Portal access</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {customers.data.items.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <strong>{c.name}</strong>
                      <div className="muted small">#{c.id}</div>
                    </td>
                    <td>{c.company || '—'}</td>
                    <td className="small">
                      <div>{c.email}</div>
                      <div className="muted">{c.phone || 'No phone'}</div>
                    </td>
                    <td>{c.user_id ? 'Linked account' : <span className="muted small">No login</span>}</td>
                    <td className="right">
                      <Button size="sm" variant="ghost" onClick={() => openEdit(c)}>Edit</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pagination page={page} pageSize={20} total={customers.data?.total || 0} onPage={setPage} />
      </Card>

      <Modal
        open={modal}
        onClose={() => setModal(false)}
        title={editing ? `Edit ${editing.name}` : 'New customer'}
        footer={
          <>
            <Button variant="ghost" onClick={() => setModal(false)}>Cancel</Button>
            <Button onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save customer'}</Button>
          </>
        }
      >
        <form onSubmit={save} className="form-stack">
          <ErrorBanner message={error} />
          <div className="grid-2">
            <Field label="Name">
              <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            </Field>
            <Field label="Email">
              <input className="input" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
            </Field>
            <Field label="Phone">
              <input className="input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            </Field>
            <Field label="Company">
              <input className="input" value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} />
            </Field>
          </div>
          <Field label="Address">
            <textarea className="input" rows="2" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
          </Field>
        </form>
      </Modal>
    </>
  )
}
