import { useState } from 'react'
import { formatDate, formatMoney } from '../api'
import { useApi } from '../hooks'
import { PageHeader, Card, Spinner, ErrorBanner, EmptyState, Pagination, Badge } from '../components/ui'

const METHODS = ['card', 'bank_transfer', 'cash', 'upi', 'cheque', 'other']

export default function Payments({ portal = false }) {
  const [page, setPage] = useState(1)
  const [method, setMethod] = useState('')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')

  const payments = useApi('/payments', {
    page,
    page_size: 20,
    method: method || undefined,
    from_date: fromDate || undefined,
    to_date: toDate || undefined,
  })

  return (
    <>
      <PageHeader
        title={portal ? 'My payments' : 'Payments'}
        subtitle={portal ? 'Payments recorded against your invoices.' : 'Every collection, with method, date and reference.'}
      />
      <Card>
        <div className="toolbar wrap">
          <select
            className="input compact"
            value={method}
            onChange={(e) => {
              setMethod(e.target.value)
              setPage(1)
            }}
          >
            <option value="">All methods</option>
            {METHODS.map((m) => <option key={m} value={m}>{m.replace('_', ' ')}</option>)}
          </select>
          <label className="inline-date">
            <span className="muted small">From</span>
            <input className="input" type="date" value={fromDate} onChange={(e) => { setFromDate(e.target.value); setPage(1) }} />
          </label>
          <label className="inline-date">
            <span className="muted small">To</span>
            <input className="input" type="date" value={toDate} onChange={(e) => { setToDate(e.target.value); setPage(1) }} />
          </label>
          <span className="muted small">{payments.data?.total ?? 0} payments</span>
        </div>
        <ErrorBanner message={payments.error} onRetry={payments.reload} />
        {payments.loading && !payments.data ? (
          <Spinner />
        ) : !payments.data?.items?.length ? (
          <EmptyState title="No payments found" hint="Payments appear here once recorded against an invoice." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Invoice</th>
                  {!portal && <th>Customer</th>}
                  <th>Method</th>
                  <th className="num">Amount</th>
                  <th>Note</th>
                </tr>
              </thead>
              <tbody>
                {payments.data.items.map((p) => (
                  <tr key={p.id}>
                    <td>{formatDate(p.date)}</td>
                    <td><strong>{p.invoice_number || '—'}</strong></td>
                    {!portal && <td>{p.customer_name || '—'}</td>}
                    <td><Badge status="quotation">{p.method.replace('_', ' ')}</Badge></td>
                    <td className="num">{formatMoney(p.amount)}</td>
                    <td className="small">{p.note || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pagination page={page} pageSize={20} total={payments.data?.total || 0} onPage={setPage} />
      </Card>
    </>
  )
}
