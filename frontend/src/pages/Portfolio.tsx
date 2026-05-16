import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { PortfolioHistory, PortfolioView } from "../types";
import { fmtMoney, fmtNum, pnlClass, signedPct } from "../util";
import { ErrorBox, Loader } from "../components/Loader";
import { AllocationChart } from "../components/AllocationChart";
import { EquityCurve } from "../components/EquityCurve";

export default function Portfolio() {
  const [data, setData] = useState<PortfolioView | null>(null);
  const [history, setHistory] = useState<PortfolioHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [view, hist] = await Promise.all([
        api.portfolio(),
        api.portfolioHistory().catch(() => null),
      ]);
      setData(view);
      setHistory(hist);
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (loading && !data) return <Loader />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;

  return (
    <>
      <div className="toolbar">
        <h1 style={{ margin: 0 }}>Portfolio</h1>
        <span className="muted">{data.name} · inception {data.inception_date}</span>
        <button onClick={load} disabled={loading} style={{ marginLeft: "auto" }}>
          Refresh
        </button>
      </div>

      <div className="kpi-row">
        <Kpi label="Equity" value={fmtMoney(data.equity)} />
        <Kpi
          label="Return"
          value={signedPct(data.total_return_pct)}
          tone={pnlClass(data.total_return_pct)}
        />
        <Kpi label="Cash" value={fmtMoney(data.cash)} />
        <Kpi label="Positions" value={String(data.position_count)} />
      </div>

      {history && history.points.length > 0 ? (
        <div className="card">
          <h3 style={{ marginBottom: "0.75rem" }}>Equity</h3>
          <EquityCurve
            points={history.points}
            startingEquity={history.starting_equity}
          />
        </div>
      ) : null}

      <div className="card">
        <h3 style={{ marginBottom: "0.75rem" }}>Allocation</h3>
        <AllocationChart cash={data.cash} positions={data.positions} />
      </div>

      <div className="card">
        <h3 style={{ marginBottom: "0.75rem" }}>Open positions</h3>
        {data.positions.length === 0 ? (
          <p className="muted">No open positions.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Side</th>
                <th className="num">Shares</th>
                <th className="num">Entry</th>
                <th className="num">Mark</th>
                <th className="num">Δ</th>
                <th className="num">Unrealized P&amp;L</th>
                <th>Entry date</th>
              </tr>
            </thead>
            <tbody>
              {data.positions.map((p) => {
                const move =
                  p.direction === "long"
                    ? (p.current_price / p.entry_price - 1) * 100
                    : (1 - p.current_price / p.entry_price) * 100;
                return (
                  <tr key={p.ticker}>
                    <td>
                      <Link to={`/tickers/${p.ticker}`}>{p.ticker}</Link>
                    </td>
                    <td>
                      <span className={`pill ${p.direction === "long" ? "bull" : "bear"}`}>
                        {p.direction}
                      </span>
                    </td>
                    <td className="num">{fmtNum(p.shares, 2)}</td>
                    <td className="num">{fmtMoney(p.entry_price)}</td>
                    <td className="num">{fmtMoney(p.current_price)}</td>
                    <td className={`num ${pnlClass(move)}`}>{signedPct(move)}</td>
                    <td className={`num ${pnlClass(p.unrealized_pnl)}`}>
                      {fmtMoney(p.unrealized_pnl, true)}
                    </td>
                    <td className="muted">{p.entry_date}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

function Kpi({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className={`kpi-value ${tone ?? ""}`}>{value}</div>
    </div>
  );
}
