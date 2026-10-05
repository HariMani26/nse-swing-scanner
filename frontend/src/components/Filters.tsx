import type { DashboardFilters } from "../types";

interface Props {
  filters: DashboardFilters;
  onChange: (filters: DashboardFilters) => void;
}

export default function Filters({ filters, onChange }: Props) {
  return (
    <section className="card filters-panel">
      <div className="filters-grid">
        <label>
          Min score
          <input
            type="number"
            min={0}
            max={100}
            value={filters.min_score ?? ""}
            onChange={(e) => onChange({ ...filters, min_score: e.target.value ? Number(e.target.value) : undefined })}
            placeholder="e.g. 80"
          />
        </label>
        <label>
          RSI min
          <input
            type="number"
            value={filters.rsi_min ?? ""}
            onChange={(e) => onChange({ ...filters, rsi_min: e.target.value ? Number(e.target.value) : undefined })}
          />
        </label>
        <label>
          RSI max
          <input
            type="number"
            value={filters.rsi_max ?? ""}
            onChange={(e) => onChange({ ...filters, rsi_max: e.target.value ? Number(e.target.value) : undefined })}
          />
        </label>
        <label>
          Setup
          <select
            value={filters.setup ?? ""}
            onChange={(e) => onChange({ ...filters, setup: e.target.value as DashboardFilters["setup"] })}
          >
            <option value="">Any</option>
            <option value="breakout">Breakout</option>
            <option value="pullback">Pullback</option>
          </select>
        </label>
        <label>
          Sector
          <input
            type="text"
            value={filters.sector ?? ""}
            onChange={(e) => onChange({ ...filters, sector: e.target.value })}
            placeholder="e.g. IT, Banking"
          />
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={!!filters.ema_bullish}
            onChange={(e) => onChange({ ...filters, ema_bullish: e.target.checked || undefined })}
          />
          Bullish EMA
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={!!filters.macd_bullish}
            onChange={(e) => onChange({ ...filters, macd_bullish: e.target.checked || undefined })}
          />
          MACD bullish
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={!!filters.volume_breakout}
            onChange={(e) => onChange({ ...filters, volume_breakout: e.target.checked || undefined })}
          />
          Volume breakout
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={!!filters.near_52w_high}
            onChange={(e) => onChange({ ...filters, near_52w_high: e.target.checked || undefined })}
          />
          Near 52-week high
        </label>
      </div>
    </section>
  );
}
