export interface StatCardProps {
  label: string;
  value: string | number;
  delta?: { value: string; positive?: boolean };
  className?: string;
}

export function StatCard({ label, value, delta, className = "" }: StatCardProps) {
  return (
    <div className={`ds-card ${className}`.trim()}>
      <p
        className="mb-2 text-[10.5px] font-semibold uppercase tracking-[0.07em]"
        style={{ color: "var(--muted)" }}
      >
        {label}
      </p>
      <p
        className="font-soehne text-2xl font-semibold tracking-[-0.03em] sm:text-[28px]"
        style={{ color: "var(--charcoal)" }}
      >
        {value}
      </p>
      {delta ? (
        <p
          className="mt-1 text-[11px] font-semibold"
          style={{ color: delta.positive === false ? "var(--red)" : "var(--green)" }}
        >
          {delta.value}
        </p>
      ) : null}
    </div>
  );
}
