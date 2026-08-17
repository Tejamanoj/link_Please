import { useEffect, useState, useCallback, type FormEvent } from 'react'
import StatusBadge from '../components/StatusBadge'
import { fetchRules, createRule, toggleRule, type Rule } from '../api'

export default function Rules() {
  const [rules, setRules] = useState<Rule[]>([])
  const [loading, setLoading] = useState(true)
  const [keyword, setKeyword] = useState('')
  const [dmMessage, setDmMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [toggling, setToggling] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setRules(await fetchRules())
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    if (!keyword.trim() || !dmMessage.trim()) {
      setError('Both keyword and DM message are required.')
      return
    }
    setSubmitting(true)
    try {
      const r = await createRule(keyword.trim(), dmMessage.trim())
      setSuccess(`Rule "${r.keyword}" created successfully!`)
      setKeyword('')
      setDmMessage('')
      await load()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create rule')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleToggle(ruleId: string) {
    setToggling(ruleId)
    try {
      await toggleRule(ruleId)
      await load()
    } catch {
      // silent
    } finally {
      setToggling(null)
    }
  }

  const SUGGESTIONS = ['PRICE', 'DISCOUNT', 'INFO', 'LINK', 'DEMO', 'COLLAB', 'CATALOG']

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      
      {/* Header */}
      <div>
        <h1 style={{ fontSize: '22px', fontWeight: 800, color: '#0f172a', letterSpacing: '-0.02em' }}>
          Keyword Automation Rules
        </h1>
        <p style={{ fontSize: '13px', color: '#64748b', marginTop: '2px' }}>
          When an Instagram comment contains a matching keyword, the configured DM will be sent automatically.
        </p>
      </div>

      {/* Create Rule Card */}
      <div
        style={{
          backgroundColor: '#ffffff',
          border: '1px solid #e2e8f0',
          borderRadius: '12px',
          padding: '24px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.04)'
        }}
      >
        <h2 style={{ fontSize: '15px', fontWeight: 700, color: '#0f172a', marginBottom: '4px' }}>
          Create New Rule
        </h2>
        <p style={{ fontSize: '12px', color: '#64748b', marginBottom: '16px' }}>
          Set up keyword triggers and automated responses for comment webhooks.
        </p>

        <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase', color: '#475569', marginBottom: '6px' }}>
              Keyword <span style={{ color: '#dc2626' }}>*</span>
            </label>
            <input
              type="text"
              value={keyword}
              onChange={e => setKeyword(e.target.value)}
              placeholder="e.g. PRICE (case-insensitive)"
              style={{
                width: '100%',
                padding: '9px 12px',
                backgroundColor: '#f8fafc',
                border: '1px solid #cbd5e1',
                borderRadius: '8px',
                fontSize: '14px',
                color: '#0f172a',
                outline: 'none'
              }}
            />

            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '8px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '11px', color: '#94a3b8' }}>Suggestions:</span>
              {SUGGESTIONS.map(s => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setKeyword(s)}
                  style={{
                    padding: '3px 10px',
                    fontSize: '11px',
                    fontWeight: 600,
                    borderRadius: '6px',
                    border: '1px solid #e2e8f0',
                    backgroundColor: keyword === s ? '#4f46e5' : '#f1f5f9',
                    color: keyword === s ? '#ffffff' : '#475569',
                    cursor: 'pointer'
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase', color: '#475569', marginBottom: '6px' }}>
              DM Message <span style={{ color: '#dc2626' }}>*</span>
            </label>
            <textarea
              value={dmMessage}
              onChange={e => setDmMessage(e.target.value)}
              placeholder="e.g. Thanks for your interest! Here is the price list: https://example.com/pricing"
              rows={3}
              style={{
                width: '100%',
                padding: '9px 12px',
                backgroundColor: '#f8fafc',
                border: '1px solid #cbd5e1',
                borderRadius: '8px',
                fontSize: '14px',
                color: '#0f172a',
                outline: 'none',
                resize: 'vertical'
              }}
            />
          </div>

          {error && <p style={{ fontSize: '12px', color: '#dc2626', backgroundColor: '#fef2f2', border: '1px solid #fecaca', padding: '8px 12px', borderRadius: '6px' }}>⚠️ {error}</p>}
          {success && <p style={{ fontSize: '12px', color: '#16a34a', backgroundColor: '#f0fdf4', border: '1px solid #bbf7d0', padding: '8px 12px', borderRadius: '6px' }}>✅ {success}</p>}

          <div>
            <button
              type="submit"
              disabled={submitting}
              style={{
                padding: '9px 20px',
                backgroundColor: '#4f46e5',
                color: '#ffffff',
                border: 'none',
                borderRadius: '8px',
                fontSize: '13px',
                fontWeight: 700,
                cursor: submitting ? 'not-allowed' : 'pointer',
                opacity: submitting ? 0.7 : 1
              }}
            >
              {submitting ? 'Creating...' : 'Create Rule'}
            </button>
          </div>
        </form>
      </div>

      {/* Rules List Cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <h2 style={{ fontSize: '15px', fontWeight: 700, color: '#0f172a' }}>
          Configured Rules ({rules.length})
        </h2>

        {loading ? (
          <div style={{ padding: '30px', textAlign: 'center', color: '#64748b', backgroundColor: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
            Loading rules…
          </div>
        ) : rules.length === 0 ? (
          <div style={{ padding: '30px', textAlign: 'center', color: '#64748b', backgroundColor: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', fontSize: '13px' }}>
            No rules created yet. Add a rule above to start matching comment keywords.
          </div>
        ) : (
          rules.map(rule => (
            <div
              key={rule.rule_id}
              style={{
                backgroundColor: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: '12px',
                padding: '18px 20px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '16px',
                opacity: rule.active ? 1 : 0.65
              }}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxWidth: '700px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                  <span
                    style={{
                      fontSize: '12px',
                      fontWeight: 800,
                      color: '#4338ca',
                      backgroundColor: '#eef2ff',
                      border: '1px solid #c7d2fe',
                      padding: '3px 10px',
                      borderRadius: '6px',
                      letterSpacing: '0.04em'
                    }}
                  >
                    KEYWORD: {rule.keyword}
                  </span>
                  <StatusBadge status={rule.active ? 'delivered' : 'cancelled'} />
                  <span style={{ fontSize: '11px', color: '#94a3b8', fontFamily: 'monospace' }}>
                    Rule ID: {rule.rule_id}
                  </span>
                </div>

                <div style={{ fontSize: '13px', color: '#334155', backgroundColor: '#f8fafc', padding: '10px 14px', borderRadius: '8px', border: '1px solid #f1f5f9', marginTop: '4px' }}>
                  "{rule.dm_message}"
                </div>
              </div>

              <div>
                <button
                  onClick={() => handleToggle(rule.rule_id)}
                  disabled={toggling === rule.rule_id}
                  style={{
                    padding: '7px 16px',
                    fontSize: '12px',
                    fontWeight: 700,
                    borderRadius: '8px',
                    border: `1px solid ${rule.active ? '#fecaca' : '#bbf7d0'}`,
                    backgroundColor: rule.active ? '#fef2f2' : '#f0fdf4',
                    color: rule.active ? '#b91c1c' : '#15803d',
                    cursor: 'pointer'
                  }}
                >
                  {toggling === rule.rule_id
                    ? 'Updating…'
                    : rule.active ? 'Pause Rule' : 'Activate Rule'}
                </button>
              </div>
            </div>
          ))
        )}
      </div>

    </div>
  )
}
