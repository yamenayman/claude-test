import { useCallback, useEffect, useState } from "react";
import { API_URL, apiGet } from "../lib/api";

function StatusDot({ ok }) {
  return <span className={`badgeDot ${ok ? "dotOk" : "dotBad"}`} />;
}

export default function StatusPage() {
  const [health, setHealth] = useState(null);
  const [ready, setReady] = useState(null);
  const [providers, setProviders] = useState(null);
  const [kg, setKg] = useState(null);
  const [checkedAt, setCheckedAt] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    const [healthResult, readyResult, providersResult, kgResult] = await Promise.allSettled([
      apiGet("/healthz"),
      fetch(`${API_URL}/readyz`).then((response) => response.json()),
      apiGet("/llm/providers"),
      apiGet("/kg/overview"),
    ]);
    setHealth(healthResult.status === "fulfilled" ? healthResult.value : null);
    setReady(readyResult.status === "fulfilled" ? readyResult.value : null);
    setProviders(providersResult.status === "fulfilled" ? providersResult.value : null);
    setKg(kgResult.status === "fulfilled" ? kgResult.value : null);
    setCheckedAt(new Date());
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const dependencies = ready ? ready.dependencies || {} : {};

  return (
    <>
      <div className="pageHead">
        <p className="eyebrow">Health · Readiness · Providers · Knowledge Graph</p>
        <h1>حالة النظام</h1>
        <p className="lede">
          مراقبة حية لخدمات المشروع: واجهة API، ومخزن المتجهات Weaviate، ومزوّد نموذج الذكاء
          الاصطناعي النشط، والرسم المعرفي.
        </p>
      </div>

      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 18, flexWrap: "wrap" }}>
        <button type="button" className="btn btnPrimary" onClick={refresh} disabled={loading}>
          {loading ? "جارٍ الفحص…" : "🔄 إعادة الفحص"}
        </button>
        {checkedAt && (
          <span className="chip">آخر فحص: {checkedAt.toLocaleTimeString("ar-JO")}</span>
        )}
      </div>

      <div className="statusGrid">
        <div className="card">
          <div className="cardTitle">
            <StatusDot ok={Boolean(health && health.status === "ok")} /> واجهة API
          </div>
          <div className="statusRow">
            <span>الخدمة</span>
            <span className="statusVal">{health ? health.service : "غير متاح"}</span>
          </div>
          <div className="statusRow">
            <span>الحالة العامة</span>
            <span className="statusVal">{ready ? ready.status : "غير متاح"}</span>
          </div>
          <div className="statusRow">
            <span>روابط</span>
            <span className="statusVal">
              <a href={`${API_URL}/docs`} target="_blank" rel="noreferrer">
                docs
              </a>
              {" · "}
              <a href={`${API_URL}/metrics/`} target="_blank" rel="noreferrer">
                metrics
              </a>
            </span>
          </div>
        </div>

        <div className="card">
          <div className="cardTitle">
            <StatusDot ok={Boolean(dependencies.retrieval && dependencies.retrieval.ok)} /> محرّك الاسترجاع
          </div>
          <div className="statusRow">
            <span>الخلفية النشطة</span>
            <span className="statusVal">
              {dependencies.retrieval
                ? dependencies.retrieval.backend === "local"
                  ? "local (BM25 + KG)"
                  : "weaviate"
                : "-"}
            </span>
          </div>
          <div className="statusRow">
            <span>جاهز</span>
            <span className="statusVal">
              {dependencies.retrieval ? String(dependencies.retrieval.ok) : "غير متاح"}
            </span>
          </div>
          {dependencies.retrieval && dependencies.retrieval.url && (
            <div className="statusRow">
              <span>العنوان</span>
              <span className="statusVal">{dependencies.retrieval.url}</span>
            </div>
          )}
        </div>

        <div className="card">
          <div className="cardTitle">
            <StatusDot ok={Boolean(dependencies.llm && dependencies.llm.ok)} /> مزوّد النموذج النشط
          </div>
          <div className="statusRow">
            <span>المزوّد</span>
            <span className="statusVal">{dependencies.llm ? dependencies.llm.provider : "-"}</span>
          </div>
          <div className="statusRow">
            <span>جاهز</span>
            <span className="statusVal">{dependencies.llm ? String(dependencies.llm.ok) : "-"}</span>
          </div>
          {providers &&
            providers.providers.map((item) => (
              <div key={item.id} className="statusRow">
                <span>
                  <StatusDot ok={item.available} /> {item.label}
                  {item.active ? " ★" : ""}
                </span>
                <span className="statusVal">{item.model || "—"}</span>
              </div>
            ))}
        </div>

        <div className="card">
          <div className="cardTitle">
            <StatusDot ok={Boolean(kg && kg.nodes > 0)} /> الرسم المعرفي
          </div>
          {kg ? (
            <>
              <div className="statusRow">
                <span>العقد / العلاقات</span>
                <span className="statusVal">
                  {kg.nodes} / {kg.edges}
                </span>
              </div>
              {Object.entries(kg.node_types || {}).map(([type, count]) => (
                <div key={type} className="statusRow">
                  <span>{type}</span>
                  <span className="statusVal">{count}</span>
                </div>
              ))}
            </>
          ) : (
            <p style={{ color: "var(--text-2)", margin: 0 }}>غير متاح.</p>
          )}
        </div>
      </div>
    </>
  );
}
