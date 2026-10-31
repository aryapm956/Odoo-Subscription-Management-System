import { useState } from 'react'
import { api } from '../api'
import { useApi } from '../hooks'
import { passwordErrors } from './Auth'
import { PageHeader, Card, Button, Field, Modal, Spinner, ErrorBanner, EmptyState, Badge } from '../components/ui'

const EMPTY = { name: '', email: '', password: '', role: 'internal' }

export default function Staff() {
  const [modal, setModal] = useState(false)
  const [form, setForm] = useState(EMPTY)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const staff = useApi('/users/staff')

  async function save(e) {
    e.preventDefault()
    setError('')
    const problems = passwordErrors(form.password)
    if (problems.length) {
      setError(`Password needs: ${problems.join(', ')}.`)
      return
    }
    setBusy(true)
    try {
      await api('/users/staff', { method: 'POST', body: form })
      setModal(false)
      setForm(EMPTY)
      staff.reload()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function toggle(user) {
    try {
      await api(`/users/staff/${user.id}`, { method: 'PATCH', body: { is_active: !user.is_active } })
      staff.reload()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <>
      <PageHeader
        title="Staff"
        subtitle="Only admins can invite internal team members."
        actions={<Button onClick={() => setModal(true)}>Invite staff</Button>}
      />
      <Card>
        <ErrorBanner message={staff.error || error} onRetry={staff.reload} />
        {staff.loading && !staff.data ? (
          <Spinner />
        ) : !staff.data?.length ? (
          <EmptyState title="No staff accounts" hint="Invite an internal user to help run billing." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {staff.data.map((user) => (
                  <tr key={user.id}>
                    <td><strong>{user.name}</strong></td>
                    <td>{user.email}</td>
                    <td><Badge status={user.role === 'admin' ? 'active' : 'quotation'}>{user.role}</Badge></td>
                    <td><Badge status={user.is_active ? 'active' : 'closed'}>{user.is_active ? 'active' : 'inactive'}</Badge></td>
                    <td className="right">
                      <Button size="sm" variant="ghost" onClick={() => toggle(user)}>
                        {user.is_active ? 'Deactivate' : 'Reactivate'}
                      </Button>
                    </td>
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
        title="Invite staff member"
        footer={
          <>
            <Button variant="ghost" onClick={() => setModal(false)}>Cancel</Button>
            <Button onClick={save} disabled={busy}>{busy ? 'Inviting…' : 'Create staff'}</Button>
          </>
        }
      >
        <form onSubmit={save} className="form-stack">
          <ErrorBanner message={error} />
          <Field label="Full name">
            <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </Field>
          <Field label="Email">
            <input className="input" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
          </Field>
          <Field label="Password" hint="More than 8 characters with uppercase, lowercase and a special character.">
            <input className="input" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
          </Field>
          <Field label="Role">
            <select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              <option value="internal">Internal staff</option>
              <option value="admin">Admin</option>
            </select>
          </Field>
        </form>
      </Modal>
    </>
  )
}
