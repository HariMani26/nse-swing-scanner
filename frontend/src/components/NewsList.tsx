import type { NewsItemOut } from "../types";

interface Props {
  news: NewsItemOut[];
}

const SENTIMENT_CLASS: Record<string, string> = {
  strongly_positive: "sentiment-positive",
  positive: "sentiment-positive",
  neutral: "sentiment-neutral",
  negative: "sentiment-negative",
  strongly_negative: "sentiment-negative",
};

export default function NewsList({ news }: Props) {
  return (
    <section className="card">
      <h2>News</h2>
      {news.length === 0 ? (
        <p className="empty-state">News data unavailable</p>
      ) : (
        <ul className="news-list">
          {news.map((item, i) => (
            <li key={i} className="news-item">
              <div className="news-headline">
                {item.url ? (
                  <a href={item.url} target="_blank" rel="noreferrer">
                    {item.headline}
                  </a>
                ) : (
                  item.headline
                )}
              </div>
              <div className="news-meta">
                <span className={SENTIMENT_CLASS[item.sentiment] ?? "sentiment-neutral"}>
                  {item.sentiment.replace("_", " ")}
                </span>
                {" · "}
                {item.source}
                {" · "}
                {new Date(item.published_at).toLocaleString()}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
