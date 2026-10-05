import { NavLink, Route, Routes } from "react-router-dom";
import { TrendingUp, Activity, Radio, List, Briefcase, History } from "lucide-react";
import TradingDesk from "./pages/TradingDesk";
import TradingMarket from "./pages/TradingMarket";
import PaperJournal from "./pages/PaperJournal";
import Watchlist from "./pages/Watchlist";

export default function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-inner">
          <span className="app-title">Indian Market <strong>Trading Copilot</strong></span>
          <nav className="app-nav" aria-label="Main navigation">
            {[{path: "/", title: "Swing Scanner", Icon: TrendingUp}, {path: "/intraday", title: "Intraday Scanner", Icon: Activity},
              {path: "/live", title: "Live Market Scanner", Icon: Radio}, {path: "/watchlist", title: "Watchlist", Icon: List},
              {path: "/positions", title: "Open Positions", Icon: Briefcase},
              {path: "/history", title: "Trade Journal", Icon: History}].map(({path, title, Icon}) =>
              <NavLink key={path} to={path} end={path === "/"} className={({isActive}) => isActive ? "active" : ""}><Icon size={18} />{title}</NavLink>)}
          </nav>
        </div>
      </header>

      <main className="app-main">
        <Routes>
          <Route path="/" element={<TradingDesk mode="swing" />} />
          <Route path="/intraday" element={<TradingDesk mode="intraday" />} />
          <Route path="/live" element={<TradingDesk mode="intraday" live />} />
          <Route path="/stocks/:symbol" element={<TradingDesk mode="swing" />} />
          <Route path="/market" element={<TradingMarket />} />
          <Route path="/positions" element={<PaperJournal view="positions" />} />
          <Route path="/risk" element={<PaperJournal view="risk" />} />
          <Route path="/history" element={<PaperJournal view="history" />} />
          <Route path="/watchlist" element={<Watchlist />} />
        </Routes>
      </main>

      <footer className="app-footer">
        Screening results are informational only and are <strong>not financial advice</strong>. This
        tool does not predict the market or guarantee profits.
      </footer>
    </div>
  );
}
