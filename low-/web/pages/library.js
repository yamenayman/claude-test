import { useEffect, useState } from "react";
import { apiGet } from "../lib/api";

const PAGE_SIZE = 10;

const SOURCE_TYPE_LABELS = {
  official_law_selected: "نص قانوني رسمي",
  explainer_guide: "دليل شارح",
};

function ChunkCard({ chunk }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <article className="card libCard">
      <div className="libMeta">
        <span
          className={`chip ${chunk.source_type === "official_law_selected" ? "chipGreen" : "chipBlue"}`}
        >
          {SOURCE_TYPE_LABELS[chunk.source_type] || chunk.source_type}
        </span>
        {chunk.articles.map((num) => (
          <span key={num} className="chip chipGold">
            § المادة {num}
          </span>
        ))}
        {chunk.source_page != null && <span className="chip">صفحة {chunk.source_page}</span>}
      </div>
      <h3 style={{ fontSize: 17 }}>{chunk.topic}</h3>
      <p className="ref">{chunk.reference}</p>
      <div className={`libText${expanded ? " expanded" : ""}`}>{chunk.text}</div>
      <button
        type="button"
        className="btn btnGhost"
        style={{ marginTop: 10 }}
        onClick={() => setExpanded((prev) => !prev)}
      >
        {expanded ? "▲ إخفاء النص الكامل" : "▼ عرض النص الكامل"}
      </button>
    </article>
  );
}

export default function LibraryPage() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [topic, setTopic] = useState("");
  const [sourceType, setSourceType] = useState("");
  const [topics, setTopics] = useState([]);
  const [page, setPage] = useState(0);
  const [data, setData] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    apiGet("/corpus/topics").then(setTopics).catch(() => setTopics([]));
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 350);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    setPage(0);
  }, [debouncedQuery, topic, sourceType]);

  useEffect(() => {
    setLoading(true);
    apiGet("/corpus/chunks", {
      q: debouncedQuery,
      topic,
      source_type: sourceType,
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
    })
      .then((result) => {
        setData(result);
        setError("");
      })
      .catch((err) => setError(err.message || "تعذر تحميل المكتبة."))
      .finally(() => setLoading(false));
  }, [debouncedQuery, topic, sourceType, page]);

  const pageCount = Math.max(1, Math.ceil(data.total / PAGE_SIZE));

  return (
    <>
      <div className="pageHead">
        <p className="eyebrow">النصوص القانونية المعتمدة في قاعدة المعرفة — للاطلاع فقط</p>
        <h1>المكتبة القانونية</h1>
        <p className="lede">
          تصفح مواد مختارة من قانون العمل الأردني رقم 8 لسنة 1996 وتعديلاته، إضافة إلى دليل شارح.
          هذه النصوص هي المصدر الوحيد الذي يعتمد عليه المساعد في إجاباته.
        </p>
      </div>

      <div className="libFilters">
        <div>
          <label htmlFor="libSearch">بحث نصي</label>
          <input
            id="libSearch"
            type="search"
            placeholder="مثال: الفصل التعسفي، الإجازة، المادة…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <div>
          <label htmlFor="libTopic">الموضوع</label>
          <select id="libTopic" value={topic} onChange={(event) => setTopic(event.target.value)}>
            <option value="">كل المواضيع ({topics.length})</option>
            {topics.map((item) => (
              <option key={item.topic} value={item.topic}>
                {item.topic} ({item.count})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="libSource">نوع المصدر</label>
          <select
            id="libSource"
            value={sourceType}
            onChange={(event) => setSourceType(event.target.value)}
          >
            <option value="">الكل</option>
            <option value="official_law_selected">نص قانوني رسمي</option>
            <option value="explainer_guide">دليل شارح</option>
          </select>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      {loading ? (
        <div className="libList">
          {[1, 2, 3].map((item) => (
            <div key={item} className="skeleton" style={{ height: 180 }} />
          ))}
        </div>
      ) : (
        <>
          <p style={{ color: "var(--text-2)", fontWeight: 700, fontSize: 14 }}>
            {data.total} نصاً قانونياً
          </p>
          <div className="libList">
            {data.items.map((chunk) => (
              <ChunkCard key={chunk.chunk_id} chunk={chunk} />
            ))}
            {data.items.length === 0 && (
              <div className="card" style={{ textAlign: "center", color: "var(--text-2)" }}>
                لا توجد نتائج مطابقة — جرّب تعديل البحث أو المرشحات.
              </div>
            )}
          </div>
          {pageCount > 1 && (
            <div className="pager">
              <button
                type="button"
                className="btn"
                disabled={page === 0}
                onClick={() => setPage((prev) => prev - 1)}
              >
                → السابق
              </button>
              <span>
                صفحة {page + 1} من {pageCount}
              </span>
              <button
                type="button"
                className="btn"
                disabled={page + 1 >= pageCount}
                onClick={() => setPage((prev) => prev + 1)}
              >
                التالي ←
              </button>
            </div>
          )}
        </>
      )}
    </>
  );
}
