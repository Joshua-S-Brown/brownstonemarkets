export function utcLabel(value: string): string {
  const date = new Date(value);
  const month = new Intl.DateTimeFormat("en-GB", {
    month: "short",
    timeZone: "UTC",
  }).format(date);
  return `${String(date.getUTCDate()).padStart(2, "0")} ${month} ${String(date.getUTCHours()).padStart(2, "0")}:${String(date.getUTCMinutes()).padStart(2, "0")}`;
}
export function UtcTime({ value }: { value: string | null | undefined }) {
  if (!value || !Number.isFinite(Date.parse(value)))
    return <span>unknown</span>;
  const date = new Date(value);
  const day = utcLabel(value);
  return (
    <time dateTime={value} title={`${value} · Local: ${date.toLocaleString()}`}>
      {day} UTC
    </time>
  );
}
