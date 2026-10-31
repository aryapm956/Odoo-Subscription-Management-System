import { Component, useState } from 'react'
import { downloadCsv, formatDate, formatMoney } from '../api'
import { useApi } from '../hooks'
import { PageHeader, Card, Button, Spinner, ErrorBanner, EmptyState, Pagination, Badge, Tabs } from '../components/ui'

class ReportsErrorBoundary extends Component {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  render() {
    if (this.state.hasError) {
      return <div className="alert alert-error" role="alert">Reports could not be displayed. Try reloading the page.</div>
    }
    return this.props.children
  }
}

const TABS = [
  { value: 'active', label: 'Active subscriptions' },
  { value: 'revenue', label: 'Revenue collected' },
  { value: 'overdue', label: 'Overdue invoices' },
]

function ReportsContent() {
  const [tab, setTab] = useState('active')
  const [page, setPage] = useState(1)
  const [planId, setPlanId] = useState('')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [exportError, setExportError] = useState('')

  const plans = useApi('/plans', { page_size: 200 })

  const path =
    tab === 'active'
      ? '/reports/active-subscriptions'
      : tab === 'revenue'
        ? '/reports/revenue'
        : '/reports/overdue-invoices'

  const params =
    tab === 'active'
      ? { page, page_size: 20, plan_id: planId || undefined }
      : tab === 'revenue'
        ? { page, page_size: 20, from_date: fromDate || undefined, to_date: toDate || undefined }
        : { page, page_size: 20 }

  const report = useApi(path, params)
  const reportMatchesTab = tab !== 'revenue' || report.data?.total_amount !== undefined
  const reportData = reportMatchesTab ? report.data : null
  const reportItems = Array.isArray(reportData?.items) ? reportData.items : []
  const reportLoading = report.loading || (!report.error && Boolean(report.data) && !reportMatchesTab)

  function changeTab(next) {
    setTab(next)
    setPage(1)
  }

  async function exportCsv() {
    setExportError('')
    try {
      if (tab === 'active') {
        await downloadCsv('/reports/export/csv', { report: 'subscriptions', status: 'active' }, 'active-subscriptions.csv')
      } else if (tab === 'revenue') {
        await downloadCsv('/reports/export/csv', { report: 'payments', from_date: fromDate || undefined, to_date: toDate || undefined }, 'revenue.csv')
      } else {
        await downloadCsv('/reports/export/csv', { report: 'invoices' }, 'invoices.csv')
      }
    } catch (err) {
      setExportError(err.message)
    }
  }

  return (
    <>
      <PageHeader
        title="Reports"
        subtitle="Active subscriptions, collections and overdue risk — exportable to CSV."
        actions={<Button variant="ghost" onClick={exportCsv}>Export CSV</Button>}
      />
      <Card>
        <Tabs tabs={TABS} value={tab} onChange={changeTab} />

        <div className="toolbar wrap">
          {tab === 'active' && (
            <select className="input compact" value={planId} onChange={(e) => { setPlanId(e.target.value); setPage(1) }}>
              <option value="">All plans</option>
              {(plans.data?.items || []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          )}
          {tab === 'revenue' && (
            <>
              <label className="inline-date">
                <span className="muted small">From</span>
                <input className="input" type="date" value={fromDate} onChange={(e) => { setFromDate(e.target.value); setPage(1) }} />
              </label>
              <label className="inline-date">
                <span className="muted small">To</span>
                <input className="input" type="date" value={toDate} onChange={(e) => { setToDate(e.target.value); setPage(1) }} />
              </label>
            </>
          )}
          <span className="muted small">
            {tab === 'revenue' && reportData?.total_amount !== undefined
              ? `${formatMoney(Number(reportData.total_amount ?? 0))} collected · ${Number(reportData.total ?? 0)} payments`
              : `${Number(reportData?.total ?? 0)} records`}
          </span>
        </div>

        <ErrorBanner message={report.error || exportError} onRetry={report.reload} />
        {reportLoading ? (
          <Spinner />
        ) : tab === 'active' ? (
          !reportItems.length ? (
            <EmptyState title="No active subscriptions" hint="Activate a subscription to see it here." />
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Number</th>
                    <th>Customer</th>
                    <th>Plan</th>
                    <th>Billing</th>
                    <th>Start</th>
                    <th>Expiry</th>
                    <th>Next billing</th>
                  </tr>
                </thead>
                <tbody>
                  {reportItems.map((row) => (
                    <tr key={row.id}>
                      <td><strong>{row.number}</strong></td>
                      <td>{row.customer}</td>
                      <td>{row.plan}</td>
                      <td><Badge status="quotation">{row.billing_period}</Badge></td>
                      <td className="small">{formatDate(row.start_date)}</td>
                      <td className="small">{formatDate(row.expiry_date)}</td>
                      <td className="small">{formatDate(row.next_billing_date)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : tab === 'revenue' ? (
          !reportItems.length ? (
            <EmptyState title="No payments in this period" hint="Adjust the date filters or record a payment." />
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Invoice</th>
                    <th>Customer</th>
                    <th>Method</th>
                    <th className="num">Amount</th>
                    <th>Note</th>
                  </tr>
                </thead>
                <tbody>
                  {reportItems.map((row) => (
                    <tr key={row.id}>
                      <td>{formatDate(row.date)}</td>
                      <td><strong>{row.invoice || '—'}</strong></td>
                      <td>{row.customer || '—'}</td>
                      <td><Badge status="quotation">{String(row.method ?? '—').replace('_', ' ')}</Badge></td>
                      <td className="num">{formatMoney(Number(row.amount ?? 0))}</td>
                      <td className="small">{row.note || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : !reportItems.length ? (
          <EmptyState title="No overdue invoices" hint="Nothing past due right now." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Customer</th>
                  <th>Subscription</th>
                  <th>Due date</th>
                  <th>Overdue</th>
                  <th className="num">Total</th>
                  <th className="num">Balance due</th>
                </tr>
              </thead>
              <tbody>
                {reportItems.map((row) => (
                  <tr key={row.id}>
                    <td><strong>{row.number}</strong></td>
                    <td>{row.customer}</td>
                    <td>{row.subscription || '—'}</td>
                    <td>{formatDate(row.due_date)}</td>
                    <td><span className="overdue-text">{row.days_overdue} days</span></td>
                    <td className="num">{formatMoney(row.total)}</td>
                    <td className="num">{formatMoney(row.balance_due)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pagination page={page} pageSize={20} total={Number(reportData?.total ?? 0)} onPage={setPage} />
      </Card>
    </>
  )
}

export default function Reports() {
  return (
    <ReportsErrorBoundary>
      <ReportsContent />
    </ReportsErrorBoundary>
  )
}
