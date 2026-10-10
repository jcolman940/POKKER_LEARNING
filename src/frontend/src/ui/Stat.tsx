import './Stat.css'

interface Props {
  label: string
  value: string
  detail?: string
}

export function Stat({ label, value, detail }: Props) {
  return (
    <div className="ui-stat">
      <div className="ui-stat-label">{label}</div>
      <div className="ui-stat-value">{value}</div>
      {detail && <div className="ui-stat-detail">{detail}</div>}
    </div>
  )
}
