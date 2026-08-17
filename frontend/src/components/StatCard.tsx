interface StatCardProps {
  label: string
  value: number | string
  color: string
  icon: string
  description?: string
}

export default function StatCard({ label, value, color, icon, description }: StatCardProps) {
  return (
    <div
      style={{
        backgroundColor: '#ffffff',
        border: '1px solid #e2e8f0',
        borderRadius: '12px',
        padding: '20px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        gap: '12px'
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span
          style={{
            fontSize: '11px',
            fontWeight: 700,
            letterSpacing: '0.05em',
            textTransform: 'uppercase',
            color: '#64748b'
          }}
        >
          {label}
        </span>
        <div
          style={{
            width: '36px',
            height: '36px',
            borderRadius: '8px',
            backgroundColor: `${color}12`,
            color: color,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '16px'
          }}
        >
          {icon}
        </div>
      </div>

      <div>
        <div style={{ fontSize: '32px', fontWeight: 800, color: '#0f172a', lineHeight: 1.1 }}>
          {value}
        </div>
        {description && (
          <p style={{ fontSize: '12px', color: '#64748b', marginTop: '6px', fontWeight: 400 }}>
            {description}
          </p>
        )}
      </div>
    </div>
  )
}
