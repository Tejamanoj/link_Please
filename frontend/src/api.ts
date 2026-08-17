// API service layer — targets backend on :8000 during dev, or relative in prod
const BASE = typeof window !== 'undefined' && (window.location.port === '5173' || window.location.hostname === 'localhost')
  ? 'http://localhost:8000'
  : ''


export interface Stats {
  sent: number
  failed: number
  queued: number
  duplicates_blocked: number
}

export interface Rule {
  rule_id: string
  keyword: string
  dm_message: string
  active: boolean
  created_at: string | null
}

export interface DMJob {
  id: number
  rule_id: string
  rule_keyword: string | null
  user_id: string
  comment_id: string
  status: string
  attempts: number
  dm_id: string | null
  last_error: string | null
  next_retry_at: string | null
  created_at: string
  updated_at: string
}

export interface WebhookEvent {
  id: number
  event_id: string
  event_type: string
  comment_id: string
  user_id: string | null
  username: string | null
  text: string | null
  status: string
  created_at: string
  processed_at: string | null
}

export async function fetchStats(): Promise<Stats> {
  const r = await fetch(`${BASE}/stats`)
  if (!r.ok) throw new Error('Failed to fetch stats')
  return r.json()
}

export async function fetchRules(): Promise<Rule[]> {
  const r = await fetch(`${BASE}/api/rules`)
  if (!r.ok) throw new Error('Failed to fetch rules')
  return r.json()
}

export async function createRule(keyword: string, dm_message: string): Promise<Rule> {
  const r = await fetch(`${BASE}/rules`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keyword, dm_message })
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail || 'Failed to create rule')
  }
  return r.json()
}

export async function toggleRule(rule_id: string): Promise<Rule> {
  const r = await fetch(`${BASE}/api/rules/${rule_id}/toggle`, { method: 'PATCH' })
  if (!r.ok) throw new Error('Failed to toggle rule')
  return r.json()
}

export async function fetchJobs(limit = 50): Promise<DMJob[]> {
  const r = await fetch(`${BASE}/api/jobs?limit=${limit}`)
  if (!r.ok) throw new Error('Failed to fetch jobs')
  return r.json()
}

export async function fetchEvents(limit = 50): Promise<WebhookEvent[]> {
  const r = await fetch(`${BASE}/api/events?limit=${limit}`)
  if (!r.ok) throw new Error('Failed to fetch events')
  return r.json()
}
