import { useCallback, useEffect, useState } from "react";
import { fetchDashboard, runScan } from "../api/client";
import type { DashboardFilters, DashboardOut } from "../types";
import MarketSummary from "../components/MarketSummary";
import Filters from "../components/Filters";
import CandidatesTable from "../components/CandidatesTable";

export default function Dashboard() {
  const [data, setData] = useState<DashboardOut | null>(null);
  const [filters, setFilters] = useState<DashboardFilters>({});
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (f: DashboardFilters) => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchDashboard(f);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(filters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  async function handleRunScan() {
    setScanning(true);
    setError(null);
    try {
      await runScan();
      await load(filters);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scan failed");
    } finally {
      setScanning(false);
    }
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <div>
          <h1>NSE Swing Scanner</h1>
          <p className="subtitle">
            Last scan:{" "}
            {data?.last_scan?.finished_at
              ? new Date(data.last_scan.finished_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }) + " IST"
              : "No scan has been run yet"}
          </p>
        </div>
        <button className="primary-button" onClick={handleRunScan} disabled={scanning}>
          {scanning ? "Scanning..." : "Run Scan"}
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {data && <MarketSummary market={data.market} />}

      <Filters filters={filters} onChange={setFilters} />

      <section className="card">
        <h2>Top Swing Candidates</h2>
        {loading ? <p>Loading...</p> : <CandidatesTable candidates={data?.candidates ?? []} />}
      </section>

      <p className="disclaimer">
        These are technical screening results only - <strong>not financial advice</strong> and not a guarantee of
        future performance.
      </p>
    </div>
  );
}
