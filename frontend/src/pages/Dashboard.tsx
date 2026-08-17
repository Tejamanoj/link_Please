import { useEffect, useState, useCallback } from 'react'
import StatCard from '../components/StatCard'
import StatusBadge from '../components/StatusBadge'
import { fetchStats, fetchJobs, fetchEvents, type Stats, type DMJob, type WebhookEvent } from '../api'

function fmtTime(dt: string | null): string {
  if (!dt) return '—'
  const d = new Date(dt)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function fmtDate(dt: string | null): string {
  if (!dt) return '—'
  const d = new Date(dt)
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [jobs, setJobs] = useState<DMJob[]>([])
  const [events, setEvents] = useState<WebhookEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date())

  const refresh = useCallback(async () => {
    try {
      const [s, j, e] = await Promise.all([fetchStats(), fetchJobs(50), fetchEvents(50)])
      setStats(s)
      setJobs(j)
      setEvents(e)
      setLastRefresh(new Date())
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 3000)
    return () => clearInterval(id)
  }, [refresh])

  if (loading) {
    return (
      <div style={{ padding: '60px 0', textAlign: 'center', color: '#64748b', fontSize: '14px' }}>
        Loading automation dashboard…
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
      
      {/* Overview Banner */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ fontSize: '22px', fontWeight: 800, color: '#0f172a', letterSpacing: '-0.02em' }}>
            System Dashboard
          </h1>
          <p style={{ fontSize: '13px', color: '#64748b', marginTop: '2px' }}>
            Live delivery metrics, active background workers, and webhook logs
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 12px',
              borderRadius: '20px',
              backgroundColor: '#f0fdf4',
              color: '#15803d',
              border: '1px solid #bbf7d0',
              fontSize: '12px',
              fontWeight: 600
            }}
          >
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#22c55e' }} />
            Worker Active
          </span>
          <span style={{ fontSize: '12px', color: '#94a3b8' }}>
            Updated {lastRefresh.toLocaleTimeString()}
          </span>
        </div>
      </div>

      {/* Metric Cards Grid */}
      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
          <StatCard
            label="Delivered DMs"
            value={stats.sent}
            color="#16a34a"
            icon="✉️"
            description="Confirmed delivered to user"
          />
          <StatCard
            label="Failed Jobs"
            value={stats.failed}
            color="#dc2626"
            icon="⚠️"
            description="Permanently failed after retries"
          />
          <StatCard
            label="Queued Jobs"
            value={stats.queued}
            color="#4f46e5"
            icon="⏳"
            description="Waiting to dispatch or retry"
          />
          <StatCard
            label="Duplicates Blocked"
            value={stats.duplicates_blocked}
            color="#d97706"
            icon="🛡️"
            description="Idempotent duplicate check"
          />
        </div>
      )}

      {/* Main Content Sections (Clean Cards) */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '24px' }}>
        
        {/* DM Dispatch Jobs Card */}
        <div
          style={{
            backgroundColor: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: '12px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
            overflow: 'hidden'
          }}
        >
          <div
            style={{
              padding: '16px 20px',
              borderBottom: '1px solid #e2e8f0',
              backgroundColor: '#f8fafc',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}
          >
            <h2 style={{ fontSize: '14px', fontWeight: 700, color: '#0f172a' }}>
              💼 Recent DM Jobs ({jobs.length})
            </h2>
            <span style={{ fontSize: '12px', color: '#64748b' }}>Sorted by recent update</span>
          </div>

          <div>
            {jobs.length === 0 ? (
              <div style={{ padding: '40px', textAlign: 'center', color: '#64748b', fontSize: '13px' }}>
                No DM jobs recorded yet. Send a matching webhook to trigger a job.
              </div>
            ) : (
              jobs.map((job, idx) => (
                <div
                  key={job.id}
                  style={{
                    padding: '14px 20px',
                    borderTop: idx > 0 ? '1px solid #f1f5f9' : 'none',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '12px'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                    {/* User Avatar Circle */}
                    <div
                      style={{
                        width: '38px',
                        height: '38px',
                        borderRadius: '50%',
                        backgroundColor: '#4f46e5',
                        color: '#ffffff',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '13px',
                        fontWeight: 700,
                        flexShrink: 0
                      }}
                    >
                      {job.user_id.replace('usr_', '').substring(0, 2).toUpperCase()}
                    </div>

                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: '14px', fontWeight: 700, color: '#0f172a' }}>
                          {job.user_id}
                        </span>
                        {job.rule_keyword && (
                          <span
                            style={{
                              fontSize: '11px',
                              fontWeight: 700,
                              color: '#4338ca',
                              backgroundColor: '#eef2ff',
                              border: '1px solid #c7d2fe',
                              padding: '2px 8px',
                              borderRadius: '4px'
                            }}
                          >
                            KEYWORD: {job.rule_keyword}
                          </span>
                        )}
                        <StatusBadge status={job.status} />
                      </div>

                      <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px', display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                        <span>Comment ID: <code style={{ backgroundColor: '#f1f5f9', padding: '2px 6px', borderRadius: '4px', color: '#334155' }}>{job.comment_id}</code></span>
                        <span>Attempts: <strong>{job.attempts}</strong></span>
                        {job.dm_id && (
                          <span>DM ID: <code style={{ backgroundColor: '#f1f5f9', padding: '2px 6px', borderRadius: '4px', color: '#334155' }}>{job.dm_id}</code></span>
                        )}
                      </div>

                      {job.last_error && (
                        <div style={{ fontSize: '11px', color: '#b91c1c', backgroundColor: '#fef2f2', border: '1px solid #fecaca', padding: '4px 8px', borderRadius: '4px', marginTop: '6px', fontFamily: 'monospace' }}>
                          ⚠️ {job.last_error}
                        </div>
                      )}
                    </div>
                  </div>

                  <div style={{ textAlign: 'right', fontSize: '12px', color: '#64748b' }}>
                    <div style={{ fontWeight: 600, color: '#334155' }}>{fmtDate(job.updated_at)} {fmtTime(job.updated_at)}</div>
                    <div style={{ fontSize: '11px', color: '#94a3b8' }}>Created {fmtTime(job.created_at)}</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Webhook Events Log Card */}
        <div
          style={{
            backgroundColor: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: '12px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
            overflow: 'hidden'
          }}
        >
          <div
            style={{
              padding: '16px 20px',
              borderBottom: '1px solid #e2e8f0',
              backgroundColor: '#f8fafc',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}
          >
            <h2 style={{ fontSize: '14px', fontWeight: 700, color: '#0f172a' }}>
              ⚡ Webhook Event Activity ({events.length})
            </h2>
            <span style={{ fontSize: '12px', color: '#64748b' }}>Ingested webhook payloads</span>
          </div>

          <div>
            {events.length === 0 ? (
              <div style={{ padding: '40px', textAlign: 'center', color: '#64748b', fontSize: '13px' }}>
                No webhook events received yet.
              </div>
            ) : (
              events.map((ev, idx) => (
                <div
                  key={ev.id}
                  style={{
                    padding: '14px 20px',
                    borderTop: idx > 0 ? '1px solid #f1f5f9' : 'none',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '12px'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div
                      style={{
                        padding: '4px 8px',
                        backgroundColor: '#f1f5f9',
                        border: '1px solid #cbd5e1',
                        borderRadius: '6px',
                        fontSize: '11px',
                        fontFamily: 'monospace',
                        fontWeight: 700,
                        color: '#475569'
                      }}
                    >
                      {ev.event_id}
                    </div>

                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                        <span
                          style={{
                            fontSize: '11px',
                            fontWeight: 600,
                            padding: '2px 8px',
                            borderRadius: '4px',
                            backgroundColor: ev.event_type === 'comment.deleted' ? '#fef2f2' : '#f0fdf4',
                            color: ev.event_type === 'comment.deleted' ? '#b91c1c' : '#15803d',
                            border: `1px solid ${ev.event_type === 'comment.deleted' ? '#fecaca' : '#bbf7d0'}`
                          }}
                        >
                          {ev.event_type}
                        </span>
                        <StatusBadge status={ev.status} />
                      </div>

                      <p style={{ fontSize: '13px', color: '#334155', marginTop: '4px', fontWeight: 500 }}>
                        "{ev.text || '(empty text)'}"
                      </p>

                      <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                        User: <strong style={{ color: '#334155' }}>{ev.username || ev.user_id || 'unknown'}</strong> • Comment: <code style={{ backgroundColor: '#f1f5f9', padding: '1px 4px', borderRadius: '3px' }}>{ev.comment_id}</code>
                      </div>
                    </div>
                  </div>

                  <div style={{ fontSize: '12px', color: '#64748b' }}>
                    {fmtTime(ev.created_at)}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

      </div>
    </div>
  )
}
