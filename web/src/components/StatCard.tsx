type StatCardProps = {
  label: string;
  value: string;
  trend?: number;
};

export default function StatCard({ label, value, trend }: StatCardProps) {
  return (
    <div className="card stat-card">
      <p className="stat-label">{label}</p>
      <div className="stat-row">
        <p className="stat-value">{value}</p>
        {trend !== undefined ? (
          <span className={`trend-badge ${trend > 0 ? "up" : "down"}`}>
            {trend > 0 ? "▲" : "▼"} {Math.abs(trend)}%
          </span>
        ) : null}
      </div>
    </div>
  );
}
