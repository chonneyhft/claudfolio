import { useMemo, useState } from "react";
import type { EquityPoint } from "../types";
import { fmtMoney, signedPct } from "../util";

const WIDTH = 720;
const HEIGHT = 220;
const PAD_L = 56;
const PAD_R = 16;
const PAD_T = 16;
const PAD_B = 28;

function fmtDateShort(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${parseInt(m, 10)}/${parseInt(d, 10)}`;
}

function niceTicks(min: number, max: number, count = 4): number[] {
  if (max <= min) return [min];
  const range = max - min;
  const step0 = range / count;
  const mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const norm = step0 / mag;
  const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
  const start = Math.ceil(min / step) * step;
  const ticks: number[] = [];
  for (let v = start; v <= max + 1e-9; v += step) ticks.push(v);
  return ticks;
}

export function EquityCurve({
  points,
  startingEquity,
}: {
  points: EquityPoint[];
  startingEquity: number;
}) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const chart = useMemo(() => {
    if (points.length === 0) return null;
    const values = points.map((p) => p.equity);
    const minV = Math.min(...values, startingEquity);
    const maxV = Math.max(...values, startingEquity);
    const pad = Math.max((maxV - minV) * 0.15, startingEquity * 0.001);
    const yMin = minV - pad;
    const yMax = maxV + pad;
    const innerW = WIDTH - PAD_L - PAD_R;
    const innerH = HEIGHT - PAD_T - PAD_B;
    const xOf = (i: number) =>
      PAD_L + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW);
    const yOf = (v: number) =>
      PAD_T + innerH - ((v - yMin) / (yMax - yMin)) * innerH;

    const linePath = points
      .map((p, i) => `${i === 0 ? "M" : "L"}${xOf(i).toFixed(2)},${yOf(p.equity).toFixed(2)}`)
      .join(" ");
    const areaPath =
      `${linePath} L${xOf(points.length - 1).toFixed(2)},${(PAD_T + innerH).toFixed(2)} ` +
      `L${xOf(0).toFixed(2)},${(PAD_T + innerH).toFixed(2)} Z`;

    const yTicks = niceTicks(yMin, yMax, 4);
    const xTickIdxs = (() => {
      if (points.length <= 6) return points.map((_, i) => i);
      const stride = Math.ceil(points.length / 6);
      const out: number[] = [];
      for (let i = 0; i < points.length; i += stride) out.push(i);
      if (out[out.length - 1] !== points.length - 1) out.push(points.length - 1);
      return out;
    })();
    const baselineY = yOf(startingEquity);

    return { xOf, yOf, linePath, areaPath, yTicks, xTickIdxs, baselineY, innerW, innerH };
  }, [points, startingEquity]);

  if (!chart || points.length === 0) {
    return <p className="muted">Not enough history yet to plot equity.</p>;
  }

  const last = points[points.length - 1];
  const totalChange = last.equity - startingEquity;
  const totalChangePct = (totalChange / startingEquity) * 100;
  const toneClass = totalChange > 0 ? "pos" : totalChange < 0 ? "neg" : "";
  const lineColor =
    totalChange > 0
      ? "var(--pos)"
      : totalChange < 0
        ? "var(--neg)"
        : "var(--fg-muted)";

  const hover = hoverIdx !== null ? points[hoverIdx] : null;

  function onMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * WIDTH;
    if (x < PAD_L || x > WIDTH - PAD_R) {
      setHoverIdx(null);
      return;
    }
    const frac = (x - PAD_L) / (WIDTH - PAD_L - PAD_R);
    const idx = Math.round(frac * (points.length - 1));
    setHoverIdx(Math.max(0, Math.min(points.length - 1, idx)));
  }

  return (
    <div className="equity">
      <div className="equity-header">
        <div>
          <div className="equity-label">Equity</div>
          <div className="equity-value">{fmtMoney(last.equity)}</div>
        </div>
        <div className={`equity-change ${toneClass}`}>
          {fmtMoney(totalChange, true)} ({signedPct(totalChangePct)})
          <span className="muted"> since inception</span>
        </div>
      </div>
      <svg
        className="equity-svg"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        preserveAspectRatio="none"
        role="img"
        aria-label="Portfolio equity over time"
        onMouseMove={onMove}
        onMouseLeave={() => setHoverIdx(null)}
      >
        <defs>
          <linearGradient id="equity-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={lineColor} stopOpacity="0.22" />
            <stop offset="100%" stopColor={lineColor} stopOpacity="0" />
          </linearGradient>
        </defs>

        {chart.yTicks.map((v) => (
          <g key={`y-${v}`}>
            <line
              x1={PAD_L}
              x2={WIDTH - PAD_R}
              y1={chart.yOf(v)}
              y2={chart.yOf(v)}
              className="equity-grid"
            />
            <text
              x={PAD_L - 8}
              y={chart.yOf(v)}
              className="equity-axis"
              textAnchor="end"
              dominantBaseline="central"
            >
              {fmtMoney(v)}
            </text>
          </g>
        ))}

        <line
          x1={PAD_L}
          x2={WIDTH - PAD_R}
          y1={chart.baselineY}
          y2={chart.baselineY}
          className="equity-baseline"
        />

        <path d={chart.areaPath} fill="url(#equity-fill)" />
        <path d={chart.linePath} fill="none" stroke={lineColor} strokeWidth="1.75" />

        {chart.xTickIdxs.map((i) => (
          <text
            key={`x-${i}`}
            x={chart.xOf(i)}
            y={HEIGHT - 8}
            className="equity-axis"
            textAnchor="middle"
          >
            {fmtDateShort(points[i].as_of)}
          </text>
        ))}

        {hover && hoverIdx !== null ? (
          <g>
            <line
              x1={chart.xOf(hoverIdx)}
              x2={chart.xOf(hoverIdx)}
              y1={PAD_T}
              y2={HEIGHT - PAD_B}
              className="equity-cursor"
            />
            <circle
              cx={chart.xOf(hoverIdx)}
              cy={chart.yOf(hover.equity)}
              r="3.5"
              fill={lineColor}
              stroke="var(--bg)"
              strokeWidth="1.5"
            />
          </g>
        ) : null}
      </svg>
      {hover ? (
        <div className="equity-tooltip">
          <span className="muted">{hover.as_of}</span>
          <span>{fmtMoney(hover.equity)}</span>
          <span className="muted">
            cash {fmtMoney(hover.cash)} · positions {fmtMoney(hover.positions_value)}
          </span>
        </div>
      ) : null}
    </div>
  );
}
