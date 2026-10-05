interface Props {
  score: number;
  label: string;
}

const LABEL_CLASS: Record<string, string> = {
  "STRONG SWING CANDIDATE": "badge badge-strong",
  WATCH: "badge badge-watch",
  NEUTRAL: "badge badge-neutral",
  "AVOID / WEAK SETUP": "badge badge-avoid",
};

export default function ScoreBadge({ score, label }: Props) {
  const className = LABEL_CLASS[label] ?? "badge badge-neutral";
  return (
    <span className={className} title="Screening result - not financial advice">
      {score.toFixed(0)} · {label}
    </span>
  );
}
