import { useState } from 'react'
import { api, formatDate, formatMoney } from '../api'
import { useApi } from '../hooks'
import { useAuth } from '../auth'
import { PageHeader, Card, Button, Spinner, ErrorBanner, EmptyState, Pagination, Badge, SuccessBanner } from '../components/ui'

const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'paid', label: 'Paid' },
  { value: 'outstanding', label: 'Outstanding' },
  { value: 'overdue', label: 'Overdue' },
  { value: 'cancelled', label: 'Cancelled' },
]

export default function Invoices({ navigate, portal = false }) {
  const { isStaff } = useAuth()
  const [page, setPage] = useState(1)
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [billing, setBilling] = useState(null)
  const [error, setError] = useState('')

  const params = {
    page,
    page_size: 20,
    search: search || undefined,
    status: ['draft', 'confirmed', 'paid', 'cancelled'].includes(filter) ? filter : undefined,
    outstanding_only: filter === 'outstanding' ? true : undefined,
    overdue_only: filter === 'overdue' ? true : undefined,
  }
  const invoices = useApi('/invoices', params)
  const detailBase = portal ? '/portal/invoices' : '/invoices'

  async function runBilling() {
    setBilling(null)
    setError('')
    try {
      const result = await api('/invoices/billing-run', { method: 'POST' })
      setBilling(`Billing run complete: ${result.created} created, ${result.skipped} skipped, ${result.failed} failed.`)
      invoices.reload()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <>
      <PageHeader
        title={portal ? 'My invoices' : 'Invoices'}
        subtitle={portal ? 'Everything Brightloop has billed you.' : 'Draft, confirmed, paid and cancelled invoices in one ledger.'}
        actions={isStaff && !portal ? <Button onClick={runBilling}>Run billing</Button> : null}
      />
      <SuccessBanner message={billing} />
      <Card>
        <div className="toolbar wrap">
          <div className="filter-pills">
            {FILTERS.map((f) => (
              <button
                key={f.value}
                className={`pill ${filter === f.value ? 'active' : ''}`}
                onClick={() => {
                  setFilter(f.value)
                  setPage(1)
                }}
              >
                {f.label}
              </button>
            ))}
          </div>
          <input
            className="input search"
            placeholder="Search invoice number…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(1)
            }}
          />
          <span className="muted small">{invoices.data?.total ?? 0} invoices</span>
        </div>
        <ErrorBanner message={invoices.error || error} onRetry={invoices.reload} />
        {invoices.loading && !invoices.data ? (
          <Spinner />
        ) : !invoices.data?.items?.length ? (
          <EmptyState title="No invoices match this view" hint="Try another filter or run billing." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Invoice</th>
                  {!portal && <th>Customer</th>}
                  <th>Period</th>
                  <th>Due date</th>
                  <th className="num">Total</th>
                  <th className="num">Paid</th>
                  <th className="num">Balance</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {invoices.data.items.map((inv) => (
                  <tr key={inv.id} className="clickable" onClick={() => navigate(`${detailBase}/${inv.id}`)}>
                    <td><strong>{inv.number}</strong></td>
                    {!portal && <td>{inv.customer_name}</td>}
                    <td className="small">{formatDate(inv.billing_period_start)} – {formatDate(inv.billing_period_end)}</td>
                    <td className="small">
                      {formatDate(inv.due_date)}
                      {inv.is_overdue && <div className="overdue-text">{inv.days_overdue} days overdue</div>}
                    </td>
                    <td className="num">{formatMoney(inv.total)}</td>
                    <td className="num">{formatMoney(inv.amount_paid)}</td>
                    <td className="num">{formatMoney(inv.balance_due)}</td>
                    <td>
                      <Badge status={inv.is_overdue ? 'overdue' : inv.status}>{inv.is_overdue ? 'overdue' : inv.status}</Badge>
                    </td>
                    <td className="right">
                      <Button size="sm" variant="ghost" onClick={(e) => { e.stopPropagation(); navigate(`${detailBase}/${inv.id}`) }}>
                        Open
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pagination page={page} pageSize={20} total={invoices.data?.total || 0} onPage={setPage} />
      </Card>
    </>
  )
}
