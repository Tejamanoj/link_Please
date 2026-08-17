interface BadgeProps {
  status: string
}

const STATUS_MAP: Record<string, { label: string; color: string; bg: string; border: string }> = {
  delivered:              { label: 'Delivered',  color: '#15803d', bg: '#f0fdf4', border: '#bbf7d0' },
  queued:                 { label: 'Queued',     color: '#4338ca', bg: '#eef2ff', border: '#c7d2fe' },
  sending:                { label: 'Sending',    color: '#1d4ed8', bg: '#eff6ff', border: '#bfdbfe' },
  waiting_retry:          { label: 'Retrying',   color: '#b45309', bg: '#fffbeb', border: '#fde68a' },
  waiting_reconciliation: { label: 'Reconciling',color: '#6b21a8', bg: '#faf5ff', border: '#e9d5ff' },
  failed:                 { label: 'Failed',     color: '#b91c1c', bg: '#fef2f2', border: '#fecaca' },
  cancelled:              { label: 'Paused',     color: '#64748b', bg: '#f8fafc', border: '#e2e8f0' },
  received:               { label: 'Received',   color: '#2563eb', bg: '#eff6ff', border: '#bfdbfe' },
  processed:              { label: 'Processed',  color: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0' },
  duplicate:              { label: 'Duplicate',  color: '#d97706', bg: '#fffbeb', border: '#fde68a' },
  deleted:                { label: 'Deleted',    color: '#64748b', bg: '#f1f5f9', border: '#cbd5e1' },
}

export default function StatusBadge({ status }: BadgeProps) {
  const cfg = STATUS_MAP[status] ?? { label: status, color: '#475569', bg: '#f8fafc', border: '#e2e8f0' }
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '3px 10px',
        borderRadius: '20px',
        fontSize: '11px',
        fontWeight: 600,
        color: cfg.color,
        backgroundColor: cfg.bg,
        border: `1px solid ${cfg.border}`,
        lineHeight: 1.2,
        whiteSpace: 'nowrap'
      }}
    >
      <span
        style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          backgroundColor: cfg.color
        }}
      />
      {cfg.label}
    </span>
  )
}
