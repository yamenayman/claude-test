import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { apiGet, apiPost } from "../lib/api";

const SAMPLE_QUESTIONS = [
  "هل يجوز إنهاء عقد العمل بدون إشعار؟",
  "ما المقصود بالفصل التعسفي؟",
  "ما حقوق العامل في الإجازة السنوية؟",
  "هل يجوز الخصم من أجر العامل؟",
  "كم عدد ساعات العمل الأسبوعية القانونية؟",
  "ما مدة إجازة الأمومة للعاملة؟",
];

const HISTORY_KEY = "lawz-history-v1";
const HISTORY_LIMIT = 12;

function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    return [];
  }
}

function saveHistory(history) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, HISTORY_LIMIT)));
  } catch (e) {
    /* storage unavailable */
  }
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="btn btnGhost"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1600);
        } catch (e) {
          /* clipboard unavailable */
        }
      }}
    >
      {copied ? "✓ تم النسخ" : "⧉ نسخ الإجابة"}
    </button>
  );
}

function AnswerCard({ entry }) {
  const result = entry.result;
  const confidence = Math.round((result.confidence || 0) * 100);
  return (
    <article className="card" style={{ marginBottom: 18 }}>
      <div className="qaQuestion">
        <span className="qMark">؟</span>
        <span>{entry.question}</span>
      </div>

      <div className="answerMeta">
        {result.provider && <span className="chip chipGreen">المزوّد: {result.provider}</span>}
        {result.model && (
          <span className="chip" style={{ direction: "ltr" }}>
            {result.model}
          </span>
        )}
        {typeof result.latency_ms === "number" && (
          <span className="chip">⏱ {(result.latency_ms / 1000).toFixed(1)} ث</span>
        )}
        {result.kg && result.kg.boosted_chunks > 0 && (
          <span className="chip chipGold">🕸 عزّز الرسم المعرفي {result.kg.boosted_chunks} نصوص</span>
        )}
      </div>

      <p className="answerText">{result.answer}</p>

      <div className="confidenceRow">
        <span>الثقة</span>
        <div className="confidenceBar">
          <div className="confidenceFill" style={{ width: `${confidence}%` }} />
        </div>
        <span style={{ fontFamily: "var(--mono)" }}>{confidence}%</span>
        <CopyButton text={result.answer} />
      </div>

      {result.kg &&
        (result.kg.question_concepts.length > 0 ||
          result.kg.related_articles.length > 0 ||
          result.kg.related_concepts.length > 0) && (
          <>
            <p className="sectionLabel">رؤى الرسم المعرفي</p>
            <div className="answerMeta" style={{ margin: 0 }}>
              {result.kg.question_concepts.map((concept) => (
                <Link
                  key={concept.id}
                  href={`/graph?node=${encodeURIComponent(concept.id)}`}
                  className="chip chipGreen chipBtn"
                >
                  🧩 {concept.label}
                </Link>
              ))}
              {result.kg.related_articles.map((num) => (
                <Link
                  key={`art-${num}`}
                  href={`/graph?node=${encodeURIComponent(`article:${num}`)}`}
                  className="chip chipGold chipBtn"
                >
                  § المادة {num}
                </Link>
              ))}
              {result.kg.related_concepts.map((concept) => (
                <Link
                  key={concept.id}
                  href={`/graph?node=${encodeURIComponent(concept.id)}`}
                  className="chip chipBtn"
                >
                  ↝ {concept.label}
                </Link>
              ))}
            </div>
          </>
        )}

      {result.citations && result.citations.length > 0 && (
        <>
          <p className="sectionLabel">المراجع المعتمدة</p>
          <ul className="citationList">
            {result.citations.map((citation) => (
              <li key={citation.chunk_id} className="citationItem">
                <strong>{citation.topic}</strong>
                <span>{citation.reference}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {result.retrieved_chunks && result.retrieved_chunks.length > 0 && (
        <>
          <p className="sectionLabel">النصوص المسترجعة ({result.retrieved_chunks.length})</p>
          <div style={{ display: "grid", gap: 8 }}>
            {result.retrieved_chunks.map((chunk) => (
              <details key={chunk.chunk_id} className="chunkDetails">
                <summary>
                  <span className="scorePill">{chunk.score.toFixed(3)}</span>
                  <span>{chunk.topic}</span>
                  {chunk.kg_concepts && chunk.kg_concepts.length > 0 && (
                    <span className="chip chipGreen" style={{ fontSize: 11.5 }}>
                      🕸 {chunk.kg_concepts.join("، ")}
                    </span>
                  )}
                </summary>
                <div className="chunkBody">
                  <p style={{ margin: "0 0 6px", fontWeight: 700 }}>{chunk.reference}</p>
                  <p style={{ margin: 0 }}>{chunk.text_preview}</p>
                </div>
              </details>
            ))}
          </div>
        </>
      )}

      <p className="disclaimer">⚠ {result.disclaimer}</p>
    </article>
  );
}

export default function Home() {
  const [question, setQuestion] = useState("");
  const [k, setK] = useState(5);
  const [provider, setProvider] = useState("");
  const [providers, setProviders] = useState([]);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");
  const timerRef = useRef(null);

  useEffect(() => {
    setHistory(loadHistory());
    apiGet("/llm/providers")
      .then((data) => setProviders(data.providers || []))
      .catch(() => setProviders([]));
    return () => clearInterval(timerRef.current);
  }, []);

  const askQuestion = useCallback(
    async (event) => {
      if (event) event.preventDefault();
      const trimmed = question.trim();
      if (trimmed.length < 2 || loading) return;

      setLoading(true);
      setError("");
      setElapsed(0);
      const started = Date.now();
      timerRef.current = setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 1000);

      try {
        const payload = { question: trimmed, k };
        if (provider) payload.provider = provider;
        const result = await apiPost("/rag/answer", payload);
        const entry = { id: `${Date.now()}`, question: trimmed, result, at: new Date().toISOString() };
        setHistory((prev) => {
          const next = [entry, ...prev].slice(0, HISTORY_LIMIT);
          saveHistory(next);
          return next;
        });
        setQuestion("");
      } catch (err) {
        setError(err.message || "تعذر الاتصال بالخدمة.");
      } finally {
        clearInterval(timerRef.current);
        setLoading(false);
      }
    },
    [question, k, provider, loading]
  );

  function clearHistory() {
    setHistory([]);
    saveHistory([]);
  }

  const activeProvider = providers.find((p) => (provider ? p.id === provider : p.active));

  return (
    <>
      <div className="pageHead">
        <p className="eyebrow">استرجاع معزّز بالرسم المعرفي · RAG + Knowledge Graph</p>
        <h1>اسأل عن قانون العمل الأردني</h1>
        <p className="lede">
          اكتب سؤالك بالعربية، وسيسترجع النظام النصوص القانونية ذات الصلة من قانون العمل الأردني رقم 8 لسنة
          1996 وتعديلاته، ويستعين بشبكة المفاهيم القانونية، ثم يولّد إجابة موثقة بالمراجع.
        </p>
      </div>

      <form onSubmit={askQuestion} className="card">
        <label htmlFor="question">سؤالك القانوني</label>
        <textarea
          id="question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) askQuestion(event);
          }}
          placeholder="مثال: هل يجوز إنهاء عقد العمل بدون إشعار؟"
        />
        <div className="askControls">
          <div className="field">
            <label htmlFor="provider">نموذج الذكاء الاصطناعي</label>
            <select id="provider" value={provider} onChange={(event) => setProvider(event.target.value)}>
              <option value="">الافتراضي (من إعدادات الخادم)</option>
              {providers.map((item) => (
                <option key={item.id} value={item.id} disabled={!item.available}>
                  {item.label}
                  {item.model ? ` — ${item.model}` : ""}
                  {item.available ? "" : " (غير مهيأ)"}
                </option>
              ))}
            </select>
          </div>
          <div className="field" style={{ maxWidth: 190 }}>
            <label htmlFor="k">عدد النصوص المسترجعة: {k}</label>
            <input
              id="k"
              type="range"
              min={1}
              max={10}
              value={k}
              onChange={(event) => setK(Number(event.target.value))}
            />
          </div>
          <button type="submit" className="btn btnPrimary" disabled={loading || question.trim().length < 2}>
            {loading ? "جارٍ توليد الإجابة…" : "اسأل الآن"}
          </button>
        </div>
        {activeProvider && !activeProvider.available && (
          <p className="error" style={{ marginTop: 12 }}>
            المزوّد المحدد غير جاهز حالياً — تحقق من صفحة حالة النظام.
          </p>
        )}
        <div className="samples">
          {SAMPLE_QUESTIONS.map((sample) => (
            <button
              key={sample}
              type="button"
              className="chip chipBtn"
              style={{ border: "1px dashed var(--border-strong)", background: "transparent" }}
              onClick={() => setQuestion(sample)}
            >
              {sample}
            </button>
          ))}
        </div>
      </form>

      {loading && (
        <div className="card loadingBox" style={{ marginTop: 18 }}>
          <div className="spinner" />
          <div>
            <strong>يجري الاسترجاع والتوليد…</strong>
            <div style={{ color: "var(--text-2)", fontSize: 14 }}>
              {elapsed} ثانية — النماذج المحلية قد تستغرق دقائق، ومزوّدو API أسرع بكثير.
            </div>
          </div>
        </div>
      )}

      {error && (
        <p className="error" style={{ marginTop: 18 }}>
          {error}
        </p>
      )}

      {history.length > 0 && (
        <>
          <div className="historyHead">
            <h2 style={{ fontSize: 20 }}>سجل الأسئلة</h2>
            <button type="button" className="btn btnGhost" onClick={clearHistory}>
              🗑 مسح السجل
            </button>
          </div>
          {history.map((entry) => (
            <AnswerCard key={entry.id} entry={entry} />
          ))}
        </>
      )}
    </>
  );
}
