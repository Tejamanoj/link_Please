import { useState } from 'react'
import Dashboard from './pages/Dashboard'
import Rules from './pages/Rules'

type Page = 'dashboard' | 'rules'

export default function App() {
  const [page, setPage] = useState<Page>('dashboard')

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f8fafc', color: '#0f172a', display: 'flex', flexDirection: 'column' }}>
      
      {/* Top Header Navbar */}
      <header style={{ backgroundColor: '#ffffff', borderBottom: '1px solid #e2e8f0', position: 'sticky', top: 0, zIndex: 50 }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 24px', height: '64px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          
          {/* Logo & Workspace Tag */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '28px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '8px',
                  backgroundColor: '#4f46e5',
                  color: '#ffffff',
                  fontWeight: 800,
                  fontSize: '16px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.1)'
                }}
              >
                L
              </div>
              <span style={{ fontWeight: 800, fontSize: '16px', color: '#0f172a', letterSpacing: '-0.02em' }}>
                LinkPlease
              </span>
              <span
                style={{
                  fontSize: '10px',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  backgroundColor: '#f1f5f9',
                  color: '#475569',
                  padding: '2px 8px',
                  borderRadius: '4px',
                  border: '1px solid #cbd5e1'
                }}
              >
                SaaS Admin
              </span>
            </div>

            {/* Navigation Bar Tabs */}
            <nav style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <button
                onClick={() => setPage('dashboard')}
                style={{
                  padding: '8px 16px',
                  fontSize: '13px',
                  fontWeight: 700,
                  borderRadius: '8px',
                  border: 'none',
                  backgroundColor: page === 'dashboard' ? '#eef2ff' : 'transparent',
                  color: page === 'dashboard' ? '#4f46e5' : '#64748b',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                📊 Dashboard & Feed
              </button>
              <button
                onClick={() => setPage('rules')}
                style={{
                  padding: '8px 16px',
                  fontSize: '13px',
                  fontWeight: 700,
                  borderRadius: '8px',
                  border: 'none',
                  backgroundColor: page === 'rules' ? '#eef2ff' : 'transparent',
                  color: page === 'rules' ? '#4f46e5' : '#64748b',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                ⚡ Automation Rules
              </button>
            </nav>
          </div>

          {/* Right Links */}
          <div>
            <a
              href="/docs"
              target="_blank"
              rel="noopener noreferrer"
              style={{
                fontSize: '12px',
                fontWeight: 600,
                color: '#64748b',
                textDecoration: 'none'
              }}
            >
              Swagger Docs ↗
            </a>
          </div>

        </div>
      </header>

      {/* Main Page Container */}
      <main style={{ maxWidth: '1200px', width: '100%', margin: '0 auto', padding: '32px 24px', flex: 1 }}>
        {page === 'dashboard' ? <Dashboard /> : <Rules />}
      </main>

    </div>
  )
}
