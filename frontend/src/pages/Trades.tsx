import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { TradeView } from "../types";
import { fmtMoney, fmtNum } from "../util";
import { ErrorBox, Loader } from "../components/Loader";

export default function Trades() {
  const [trades, setTrades] = useState<TradeView[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [limit, setLimit] = useState(50);

  async function load(n: number) {
    setLoading(true);
    setError(null);
    try {
      const r = await api.trades(n);
      setTrades(r.trades);
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(limit);
  }, [limit]);

  return (
    <>
      <div className="toolbar">
        <h1 style={{ margin: 0 }}>Trades</h1>
        <select
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
        >
          <option value={20}>Last 20</option>
          <option value={50}>Last 50</option>
          <option value={100}>Last 100</option>
          <option value={250}>Last 250</option>
        </select>
        <button
          onClick={() => load(limit)}
          disabled={loading}
          style={{ marginLeft: "auto" }}
        >
          Refresh
        </button>
      </div>

      {error ? <ErrorBox error={error} /> : null}
      {loading && !trades ? <Loader /> : null}

      {trades && trades.length === 0 ? (
        <p className="muted">No trades yet.</p>
      ) : null}

      {trades && trades.length > 0 ? (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Ticker</th>
                <th>Action</th>
                <th>Side</th>
                <th className="num">Shares</th>
                <th className="num">Price</th>
                <th>Reasoning</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((t, i) => (
                <tr key={i}>
                  <td className="muted">{t.trade_date}</td>
                  <td>
                    <Link to={`/tickers/${t.ticker}`}>{t.ticker}</Link>
                  </td>
                  <td>
                    <span className={`pill ${actionTone(t.action)}`}>
                      {t.action}
                    </span>
                  </td>
                  <td>
                    <span className={`pill ${t.direction === "long" ? "bull" : "bear"}`}>
                      {t.direction}
                    </span>
                  </td>
                  <td className="num">{fmtNum(t.shares, 2)}</td>
                  <td className="num">{fmtMoney(t.price)}</td>
                  <td className="reasoning">{t.reasoning || <span className="muted">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </>
  );
}

function actionTone(action: string): string {
  if (action === "open") return "bull";
  if (action === "close") return "bear";
  return "neutral";
}
