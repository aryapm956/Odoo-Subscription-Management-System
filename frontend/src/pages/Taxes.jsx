import { useState } from 'react'
import { api } from '../api'
import { useApi } from '../hooks'
import { useAuth } from '../auth'
import { PageHeader, Card, Button, Field, Modal, Spinner, ErrorBanner, EmptyState, Badge } from '../components/ui'

export default function Taxes() {
  const { isAdmin } = useAuth()
  const [modal, setModal] = useState(false)
  const [form, setForm] = useState({ name: '', rate_percent: '', is_default: false })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const taxes = useApi('/taxes')

  async function save(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api('/taxes', {
        method: 'POST',
        body: { name: form.name, rate_percent: Number(form.rate_percent || 0), is_default: form.is_default },
      })
      setModal(false)
      setForm({ name: '', rate_percent: '', is_default: false })
      taxes.reload()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function toggleDefault(tax) {
    try {
      await api(`/taxes/${tax.id}`, { method: 'PUT', body: { is_default: true } })
      taxes.reload()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <>
      <PageHeader
        title="Taxes"
        subtitle="Admin-defined rates applied automatically to invoices."
        actions={isAdmin && <Button onClick={() => setModal(true)}>New tax</Button>}
      />
      <Card>
        <ErrorBanner message={taxes.error || error} onRetry={taxes.reload} />
        {taxes.loading && !taxes.data ? (
          <Spinner />
        ) : !taxes.data?.length ? (
          <EmptyState title="No taxes configured" hint="Add GST or another rate to apply it automatically." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Tax</th>
                  <th className="num">Rate</th>
                  <th>Status</th>
                  {isAdmin && <th />}
                </tr>
              </thead>
              <tbody>
                {taxes.data.map((tax) => (
                  <tr key={tax.id}>
                    <td>
                      <strong>{tax.name}</strong>
                      {tax.is_default && <div className="muted small">Default tax for new subscriptions</div>}
                    </td>
                    <td className="num">{tax.rate_percent}%</td>
                    <td><Badge status={tax.is_active ? 'active' : 'closed'}>{tax.is_active ? 'active' : 'inactive'}</Badge></td>
                    {isAdmin && (
                      <td className="right">
                        {!tax.is_default && (
                          <Button size="sm" variant="ghost" onClick={() => toggleDefault(tax)}>
                            Make default
                          </Button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Modal
        open={modal}
        onClose={() => setModal(false)}
        title="New tax"
        footer={
          <>
            <Button variant="ghost" onClick={() => setModal(false)}>Cancel</Button>
            <Button onClick={save} loading={busy}>{busy ? 'Saving…' : 'Save tax'}</Button>
          </>
        }
      >
        <form onSubmit={save} className="form-stack">
          <ErrorBanner message={error} />
          <Field label="Tax name">
            <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required placeholder="GST 18%" />
          </Field>
          <Field label="Rate (%)">
            <input className="input" type="number" min="0" step="0.01" value={form.rate_percent} onChange={(e) => setForm({ ...form, rate_percent: e.target.value })} required />
          </Field>
          <label className="check">
            <input type="checkbox" checked={form.is_default} onChange={(e) => setForm({ ...form, is_default: e.target.checked })} />
            Use as the default tax
          </label>
        </form>
      </Modal>
    </>
  )
}
