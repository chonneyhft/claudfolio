import { NavLink, Route, Routes } from "react-router-dom";
import Watchlist from "./pages/Watchlist";
import TickerDetail from "./pages/TickerDetail";
import Briefing from "./pages/Briefing";
import Portfolio from "./pages/Portfolio";
import Trades from "./pages/Trades";

const navItems = [
  { to: "/", label: "Portfolio", end: true },
  { to: "/watchlist", label: "Watchlist" },
  { to: "/trades", label: "Trades" },
  { to: "/briefing", label: "Briefing" },
];

export default function App() {
  return (
    <>
      <nav className="topnav">
        <span className="brand">SFE</span>
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              isActive ? "navlink active" : "navlink"
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<Portfolio />} />
          <Route path="/watchlist" element={<Watchlist />} />
          <Route path="/trades" element={<Trades />} />
          <Route path="/tickers/:symbol" element={<TickerDetail />} />
          <Route path="/briefing" element={<Briefing />} />
          <Route path="/briefing/:date" element={<Briefing />} />
          <Route path="*" element={<p className="muted">Not found.</p>} />
        </Routes>
      </main>
    </>
  );
}
