import { useEffect } from 'react'
import { useAuth } from './auth'
import { useRoute } from './hooks'
import { Badge } from './components/ui'
import { LoginPage, SignupPage, ForgotPasswordPage, ResetPasswordPage, DevOutboxPage } from './pages/Auth'
import Dashboard from './pages/Dashboard'
import Products from './pages/Products'
import Plans from './pages/Plans'
import Taxes from './pages/Taxes'
import Templates from './pages/Templates'
import Discounts from './pages/Discounts'
import Customers from './pages/Customers'
import Staff from './pages/Staff'
import Subscriptions from './pages/Subscriptions'
import SubscriptionDetail from './pages/SubscriptionDetail'
import Invoices from './pages/Invoices'
import InvoiceDetail from './pages/InvoiceDetail'
import Payments from './pages/Payments'
import Reports from './pages/Reports'
import './App.css'

const ADMIN_NAV = [
  {
    section: 'Overview',
    items: [
      { label: 'Dashboard', path: '/dashboard' },
      { label: 'Reports', path: '/reports' },
    ],
  },
  {
    section: 'Billing',
    items: [
      { label: 'Subscriptions', path: '/subscriptions' },
      { label: 'Invoices', path: '/invoices' },
      { label: 'Payments', path: '/payments' },
    ],
  },
  {
    section: 'Catalog',
    items: [
      { label: 'Products', path: '/products' },
      { label: 'Plans', path: '/plans' },
      { label: 'Taxes', path: '/taxes' },
      { label: 'Quote Templates', path: '/templates' },
      { label: 'Discounts', path: '/discounts' },
    ],
  },
  {
    section: 'People',
    items: [
      { label: 'Customers', path: '/customers' },
      { label: 'Staff', path: '/staff' },
    ],
  },
  { section: 'Tools', items: [{ label: 'Dev Outbox', path: '/dev-outbox' }] },
]

const INTERNAL_NAV = [
  {
    section: 'Overview',
    items: [
      { label: 'Dashboard', path: '/dashboard' },
      { label: 'Reports', path: '/reports' },
    ],
  },
  {
    section: 'Billing',
    items: [
      { label: 'Subscriptions', path: '/subscriptions' },
      { label: 'Invoices', path: '/invoices' },
      { label: 'Payments', path: '/payments' },
    ],
  },
  {
    section: 'People',
    items: [{ label: 'Customers', path: '/customers' }],
  },
  { section: 'Tools', items: [{ label: 'Dev Outbox', path: '/dev-outbox' }] },
]

const CUSTOMER_NAV = [
  {
    section: 'My account',
    items: [
      { label: 'My Subscriptions', path: '/portal/subscriptions' },
      { label: 'My Invoices', path: '/portal/invoices' },
      { label: 'My Payments', path: '/portal/payments' },
    ],
  },
]

function Shell({ path, navigate, children }) {
  const { user, logout } = useAuth()
  const nav = user.role === 'admin' ? ADMIN_NAV : user.role === 'internal' ? INTERNAL_NAV : CUSTOMER_NAV
  const active = (itemPath) => path === itemPath || path.startsWith(`${itemPath}/`)

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" onClick={() => navigate(user.role === 'customer' ? '/portal/subscriptions' : '/dashboard')}>
          <span className="brand-mark">B</span>
          <span>
            <strong>Brightloop</strong>
            <small>Subscription OS</small>
          </span>
        </button>
        <nav>
          {nav.map((group) => (
            <div key={group.section} className="nav-group">
              <div className="nav-section">{group.section}</div>
              {group.items.map((item) => (
                <button
                  key={item.path}
                  className={`nav-item ${active(item.path) ? 'active' : ''}`}
                  onClick={() => navigate(item.path)}
                >
                  <span className="nav-dot" />
                  {item.label}
                </button>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="user-chip">
            <span className="avatar">{(user.name || '?').slice(0, 1).toUpperCase()}</span>
            <span className="user-meta">
              <strong>{user.name}</strong>
              <small>{user.role}</small>
            </span>
          </div>
          <button className="btn btn-ghost btn-sm full" onClick={logout}>
            Sign out
          </button>
        </div>
      </aside>
      <div className="main-area">
        <header className="topbar">
          <div className="topbar-title">
            {user.role === 'customer' ? 'Customer Portal' : user.role === 'admin' ? 'Admin workspace' : 'Internal workspace'}
          </div>
          <div className="topbar-right">
            <Badge status={user.role === 'admin' ? 'active' : user.role === 'internal' ? 'quotation' : 'draft'}>
              {user.role}
            </Badge>
            <span className="muted small">{user.name}</span>
          </div>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  )
}

function AuthRouter({ path, params, navigate }) {
  if (path === '/signup') return <SignupPage navigate={navigate} />
  if (path === '/forgot-password') return <ForgotPasswordPage navigate={navigate} />
  if (path === '/reset-password') return <ResetPasswordPage navigate={navigate} params={params} />
  if (path === '/dev-outbox') return <DevOutboxPage navigate={navigate} />
  return <LoginPage navigate={navigate} />
}

function AppRouter({ path, params, navigate }) {
  const { user } = useAuth()
  const detail = path.match(/^\/(?:portal\/)?subscriptions\/(\d+)$/)
  const invoiceDetail = path.match(/^\/(?:portal\/)?invoices\/(\d+)$/)

  if (detail) return <SubscriptionDetail id={Number(detail[1])} navigate={navigate} />
  if (invoiceDetail) return <InvoiceDetail id={Number(invoiceDetail[1])} navigate={navigate} />

  if (user.role === 'customer') {
    if (path === '/portal/invoices') return <Invoices portal />
    if (path === '/portal/payments') return <Payments portal />
    if (path === '/portal/subscriptions' || path === '/') return <Subscriptions portal />
    if (path === '/dev-outbox') return <DevOutboxPage navigate={navigate} />
    return <Subscriptions portal />
  }

  switch (path) {
    case '/dashboard':
      return <Dashboard navigate={navigate} />
    case '/reports':
      return <Reports />
    case '/subscriptions':
      return <Subscriptions navigate={navigate} />
    case '/invoices':
      return <Invoices navigate={navigate} />
    case '/payments':
      return <Payments />
    case '/customers':
      return <Customers />
    case '/products':
      return <Products />
    case '/plans':
      return <Plans />
    case '/taxes':
      return <Taxes />
    case '/templates':
      return <Templates />
    case '/discounts':
      return <Discounts />
    case '/staff':
      return <Staff />
    case '/dev-outbox':
      return <DevOutboxPage navigate={navigate} />
    default:
      return <Dashboard navigate={navigate} />
  }
}

export default function App() {
  const { user } = useAuth()
  const { path, params, navigate } = useRoute()

  useEffect(() => {
    if (user && (path === '/' || path === '/login' || path === '/signup')) {
      navigate(user.role === 'customer' ? '/portal/subscriptions' : '/dashboard')
    }
  }, [user, path, navigate])

  if (!user) return <AuthRouter path={path} params={params} navigate={navigate} />

  return (
    <Shell path={path} navigate={navigate}>
      <AppRouter path={path} params={params} navigate={navigate} />
    </Shell>
  )
}
