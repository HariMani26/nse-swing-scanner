import { useState } from "react";
import { importCsv, previewCsv, suggestMapping } from "../api/client";
import type { CsvImportResult, CsvPreviewOut } from "../types";

const TARGET_FIELDS = ["symbol", "company_name", "sector"] as const;

export default function CsvImport() {
  const [preview, setPreview] = useState<CsvPreviewOut | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [mode, setMode] = useState<"add" | "replace">("add");
  const [result, setResult] = useState<CsvImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setResult(null);
    setBusy(true);
    try {
      const p = await previewCsv(file);
      setPreview(p);
      const guessed = await suggestMapping(p.columns);
      setMapping(guessed);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to read CSV");
    } finally {
      setBusy(false);
    }
  }

  async function handleImport() {
    if (!preview) return;
    setError(null);
    setBusy(true);
    try {
      const res = await importCsv(preview.rows, mapping, mode);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="csv-import-page">
      <h1>Import Stock Universe from CSV</h1>
      <p className="subtitle">
        Upload a CSV of NSE stocks (e.g. your 52-week-high screener export, or a NIFTY 500 list). Column names
        don't need to match exactly - map them below.
      </p>

      <section className="card">
        <input type="file" accept=".csv" onChange={handleFile} disabled={busy} />
      </section>

      {error && <div className="error-banner">{error}</div>}

      {preview && (
        <section className="card">
          <h2>Column mapping ({preview.row_count} rows found)</h2>
          <div className="mapping-grid">
            {TARGET_FIELDS.map((field) => (
              <label key={field}>
                {field.replace("_", " ")}
                <select
                  value={mapping[field] ?? ""}
                  onChange={(e) => setMapping({ ...mapping, [field]: e.target.value })}
                >
                  <option value="">(none)</option>
                  {preview.columns.map((col) => (
                    <option key={col} value={col}>
                      {col}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>

          <div className="mode-select">
            <label>
              <input type="radio" checked={mode === "add"} onChange={() => setMode("add")} /> Add to existing
              universe
            </label>
            <label>
              <input type="radio" checked={mode === "replace"} onChange={() => setMode("replace")} /> Replace existing
              universe
            </label>
          </div>

          <h3>Preview (first 20 rows)</h3>
          <div className="table-scroll">
            <table className="candidates-table">
              <thead>
                <tr>
                  {preview.columns.map((c) => (
                    <th key={c}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.slice(0, 20).map((row, i) => (
                  <tr key={i}>
                    {preview.columns.map((c) => (
                      <td key={c}>{row[c]}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <button className="primary-button" onClick={handleImport} disabled={busy || !mapping.symbol}>
            {busy ? "Importing..." : "Import"}
          </button>
          {!mapping.symbol && <p className="hint">Please map a "symbol" column before importing.</p>}
        </section>
      )}

      {result && (
        <section className="card success-banner">
          Imported {result.imported} stocks ({result.skipped} skipped). Universe now has {result.total_universe}{" "}
          active stocks. Mode: {result.mode}.
        </section>
      )}
    </div>
  );
}
