interface Props {
  reasons: string[];
  warnings: string[];
}

export default function ReasonList({ reasons, warnings }: Props) {
  return (
    <section className="card">
      <h2>Reason for Score</h2>
      <ul className="reason-list">
        {reasons.map((r, i) => (
          <li key={i} className="reason-positive">
            ✓ {r}
          </li>
        ))}
      </ul>

      {warnings.length > 0 && (
        <>
          <h3>Warnings</h3>
          <ul className="reason-list">
            {warnings.map((w, i) => (
              <li key={i} className="reason-warning">
                ⚠ {w}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
