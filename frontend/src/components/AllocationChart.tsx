import type { PositionView } from "../types";
import { fmtMoney, fmtPct } from "../util";

interface Slice {
  label: string;
  value: number;
  kind: "cash" | "long" | "short";
}

const LONG_PALETTE = [
  "#3eaf5d",
  "#4ec9b0",
  "#5aa1ff",
  "#9b7bff",
  "#d18bff",
  "#f0b429",
  "#ff8a5b",
];
const SHORT_PALETTE = [
  "#e5484d",
  "#ec6675",
  "#f3849c",
];
const CASH_COLOR = "#5a5a5a";

function colorFor(slice: Slice, longIdx: number, shortIdx: number): string {
  if (slice.kind === "cash") return CASH_COLOR;
  if (slice.kind === "long") return LONG_PALETTE[longIdx % LONG_PALETTE.length];
  return SHORT_PALETTE[shortIdx % SHORT_PALETTE.length];
}

export function AllocationChart({
  cash,
  positions,
}: {
  cash: number;
  positions: PositionView[];
}) {
  const cashSlice: Slice = { label: "Cash", value: Math.max(cash, 0), kind: "cash" };
  const posSlices: Slice[] = positions.map((p) => ({
    label: p.ticker,
    value: Math.max(p.shares * p.current_price, 0),
    kind: p.direction,
  }));
  const slices: Slice[] = [cashSlice, ...posSlices].filter((s) => s.value > 0);

  const total = slices.reduce((a, s) => a + s.value, 0);

  if (total <= 0) {
    return <p className="muted">No allocation to display.</p>;
  }

  let longIdx = 0;
  let shortIdx = 0;
  const colored = slices.map((slice) => {
    let c: string;
    if (slice.kind === "cash") c = CASH_COLOR;
    else if (slice.kind === "long") c = colorFor(slice, longIdx++, 0);
    else c = colorFor(slice, 0, shortIdx++);
    return { ...slice, color: c, pct: (slice.value / total) * 100 };
  });

  return (
    <div className="alloc">
      <div
        className="alloc-bar"
        role="img"
        aria-label="Portfolio allocation by market value"
      >
        {colored.map((s) => (
          <div
            key={`${s.kind}-${s.label}`}
            className="alloc-seg"
            style={{ width: `${s.pct}%`, background: s.color }}
            title={`${s.label} · ${fmtMoney(s.value)} · ${fmtPct(s.pct, 1)}`}
          />
        ))}
      </div>
      <ul className="alloc-legend">
        {colored.map((s) => (
          <li key={`legend-${s.kind}-${s.label}`}>
            <span className="alloc-swatch" style={{ background: s.color }} />
            <span className="alloc-label">
              {s.label}
              {s.kind === "short" ? (
                <span className="muted"> · short</span>
              ) : null}
            </span>
            <span className="alloc-pct">{fmtPct(s.pct, 1)}</span>
            <span className="alloc-value muted">{fmtMoney(s.value)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
