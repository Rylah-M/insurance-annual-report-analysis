export function DataCard({
  label,
  value,
  note
}: {
  label: string;
  value: string | number;
  note?: string;
}) {
  return (
    <div className="data-card">
      <span>{label}</span>
      <strong>{value}</strong>
      {note && <small>{note}</small>}
    </div>
  );
}

export function formatValue(value: number | null | undefined, unit?: string | null) {
  if (value === null || value === undefined) return "暂无";
  const display = Number.isInteger(value) ? value.toLocaleString() : value.toFixed(2);
  return `${display}${unit ?? ""}`;
}
