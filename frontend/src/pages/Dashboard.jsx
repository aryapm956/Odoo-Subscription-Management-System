import { useApi } from '../hooks'
import { formatMoney } from '../api'
import { Card, PageHeader, Spinner, ErrorBanner, Button, AnimatedNumber } from '../components/ui'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function Kpi({ label, value, hint, tone = '', currency = false }) {
  return (
    <div className={`kpi ${tone}`}>
      <span className="kpi-label">{label}</span>
      <strong className="kpi-value"><AnimatedNumber value={value} currency={currency} /></strong>
      {hint && <span className="kpi-hint">{hint}</span>}
    </div>
  )
}

export default function Dashboard({ navigate }) {
  const { data, loading, error, reload } = useApi('/reports/dashboard')

  if (loading && !data) return <Spinner />
  if (error) return <ErrorBanner message={error} onRetry={reload} />

  const kpis = data?.kpis || {}
  const revenue = data?.revenue_by_month || []
  const maxRevenue = Math.max(1, ...revenue.map((r) => r.revenue))
  const statuses = data?.subscriptions_by_status || []
  const maxStatus = Math.max(1, ...statuses.map((s) => s.count))

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle="A live view of recurring revenue, collections and risk."
        actions={
          <>
            <Button variant="ghost" onClick={() => navigate('/reports')}>
              Open reports
            </Button>
            <Button onClick={() => navigate('/invoices')}>Billing & invoices</Button>
          </>
        }
      />

      <div className="kpi-grid">
        <Kpi label="Active subscriptions" value={kpis.active_subscriptions ?? 0} hint="Excluding drafts and closed" tone="tone-indigo" />
        <Kpi label="Monthly recurring revenue" value={kpis.mrr ?? 0} hint="Normalized from daily / weekly / yearly" tone="tone-green" currency />
        <Kpi label="Revenue collected" value={kpis.total_revenue ?? 0} hint="All recorded payments" tone="tone-blue" currency />
        <Kpi label="Outstanding" value={kpis.total_outstanding ?? 0} hint="Confirmed invoices with a balance" tone="tone-amber" currency />
        <Kpi label="Overdue invoices" value={kpis.overdue_count ?? 0} hint={`${formatMoney(kpis.overdue_amount)} past due`} tone="tone-red" />
      </div>

      <div className="grid-2">
        <Card title="Revenue collected" subtitle="Last 12 months">
          {revenue.length === 0 ? (
            <p className="muted">No payments recorded yet.</p>
          ) : (
            <div className="bar-chart">
              {revenue.map((row) => (
                <div className="bar-col" key={`${row.year}-${row.month}`}>
                  <div className="bar-wrap">
                    <div
                      className="bar"
                      style={{ height: `${Math.max(4, (row.revenue / maxRevenue) * 100)}%`, animationDelay: `${revenue.indexOf(row) * 25}ms` }}
                      data-tooltip={formatMoney(row.revenue)}
                      title={formatMoney(row.revenue)}
                      aria-label={`${MONTHS[row.month - 1]} ${row.year}: ${formatMoney(row.revenue)}`}
                    />
                  </div>
                  <span className="bar-label">
                    {MONTHS[row.month - 1]} {String(row.year).slice(2)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card
          title="Subscriptions by status"
          subtitle="Where the book stands right now"
          actions={
            <Button size="sm" variant="ghost" onClick={() => navigate('/subscriptions')}>
              View all
            </Button>
          }
        >
          {statuses.length === 0 ? (
            <p className="muted">No subscriptions yet.</p>
          ) : (
            <div className="status-bars">
              {statuses.map((row) => (
                <div className="status-bar-row" key={row.status}>
                  <span>{row.status}</span>
                  <div className="track">
                    <div
                      className={`fill fill-${row.status}`}
                      style={{ width: `${(row.count / maxStatus) * 100}%`, animationDelay: `${statuses.indexOf(row) * 35}ms` }}
                      data-tooltip={`${row.count} ${row.status}`}
                    />
                  </div>
                  <strong>{row.count}</strong>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Card
        title="Overdue watchlist"
        subtitle="Chase these before they turn into lost revenue"
        actions={
          <Button size="sm" variant="danger" onClick={() => navigate('/invoices')}>
            Review invoices
          </Button>
        }
      >
        <div className="quick-actions">
          <button className="quick-card" onClick={() => navigate('/invoices')}>
            <strong>{kpis.overdue_count ?? 0} overdue</strong>
            <span>{formatMoney(kpis.overdue_amount)} outstanding past due date</span>
          </button>
          <button className="quick-card" onClick={() => navigate('/payments')}>
            <strong>{formatMoney(kpis.total_revenue)} collected</strong>
            <span>Record a payment from an invoice</span>
          </button>
          <button className="quick-card" onClick={() => navigate('/reports')}>
            <strong>{formatMoney(kpis.mrr)} MRR</strong>
            <span>See active subscriptions and export CSV</span>
          </button>
        </div>
      </Card>
    </>
  )
}
