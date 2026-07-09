import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/router";
import ForceGraph, { TYPE_COLORS, TYPE_LABELS } from "../components/ForceGraph";
import { apiGet } from "../lib/api";

const ALL_TYPES = ["concept", "article", "topic", "source"];

export default function GraphPage() {
  const router = useRouter();
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [stats, setStats] = useState(null);
  const [types, setTypes] = useState(ALL_TYPES);
  const [selectedId, setSelectedId] = useState(null);
  const [nodeDetail, setNodeDetail] = useState(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    Promise.all([
      apiGet("/kg/graph", { types: types.join(","), limit: 400 }),
      apiGet("/kg/overview"),
    ])
      .then(([graphData, overview]) => {
        setGraph(graphData);
        setStats(overview);
        setError("");
      })
      .catch((err) => setError(err.message || "تعذر تحميل الرسم المعرفي."))
      .finally(() => setLoading(false));
  }, [types]);

  // Deep-link: /graph?node=concept:xyz
  useEffect(() => {
    if (router.isReady && router.query.node) {
      setSelectedId(String(router.query.node));
    }
  }, [router.isReady, router.query.node]);

  useEffect(() => {
    if (!selectedId) {
      setNodeDetail(null);
      return;
    }
    apiGet(`/kg/node/${encodeURIComponent(selectedId)}`)
      .then(setNodeDetail)
      .catch(() => setNodeDetail(null));
  }, [selectedId]);

  const toggleType = useCallback((type) => {
    setTypes((prev) => {
      const next = prev.includes(type) ? prev.filter((item) => item !== type) : [...prev, type];
      return next.length === 0 ? prev : next;
    });
  }, []);

  const handleSelect = useCallback((nodeId) => setSelectedId(nodeId), []);

  const selectedNode = useMemo(
    () => graph.nodes.find((node) => node.id === selectedId) || (nodeDetail ? nodeDetail.node : null),
    [graph.nodes, selectedId, nodeDetail]
  );

  return (
    <>
      <div className="pageHead">
        <p className="eyebrow">Knowledge Graph · رسم معرفي مشتق آلياً من نصوص القانون</p>
        <h1>شبكة المعرفة القانونية</h1>
        <p className="lede">
          مفاهيم قانون العمل الأردني وموادّه ومواضيعه ومصادره كشبكة مترابطة. انقر أي عقدة لاستعراض
          جيرانها، واسحب للتحريك، واستخدم عجلة الفأرة للتقريب.
        </p>
      </div>

      {error && <p className="error" style={{ marginBottom: 16 }}>{error}</p>}

      <div className="kgLayout">
        <div className="kgCanvasWrap">
          {loading ? (
            <div className="skeleton" style={{ height: 640 }} />
          ) : (
            <ForceGraph
              nodes={graph.nodes}
              edges={graph.edges}
              selectedId={selectedId}
              onSelect={handleSelect}
              highlightQuery={query}
            />
          )}
          <div className="kgLegend">
            {ALL_TYPES.map((type) => (
              <span key={type}>
                <span className="badgeDot" style={{ background: TYPE_COLORS[type] }} />
                {TYPE_LABELS[type]}
              </span>
            ))}
          </div>
        </div>

        <aside className="kgSide">
          <div className="card">
            <div className="cardTitle">🔍 بحث وتصفية</div>
            <input
              type="search"
              placeholder="ابحث عن مفهوم أو مادة…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <div className="kgFilters" style={{ marginTop: 12 }}>
              {ALL_TYPES.map((type) => (
                <button
                  key={type}
                  type="button"
                  className={`chip chipBtn${types.includes(type) ? " chipGreen" : ""}`}
                  onClick={() => toggleType(type)}
                >
                  <span className="badgeDot" style={{ background: TYPE_COLORS[type] }} />
                  {TYPE_LABELS[type]}
                </button>
              ))}
            </div>
          </div>

          {stats && (
            <div className="card">
              <div className="cardTitle">📊 نظرة عامة</div>
              <div className="kgStatGrid">
                <div className="statTile">
                  <div className="num">{stats.nodes}</div>
                  <div className="lbl">عقدة</div>
                </div>
                <div className="statTile">
                  <div className="num">{stats.edges}</div>
                  <div className="lbl">علاقة</div>
                </div>
                <div className="statTile">
                  <div className="num">{stats.node_types.concept || 0}</div>
                  <div className="lbl">مفهوم قانوني</div>
                </div>
                <div className="statTile">
                  <div className="num">{stats.node_types.article || 0}</div>
                  <div className="lbl">مادة قانونية</div>
                </div>
              </div>
            </div>
          )}

          <div className="card">
            <div className="cardTitle">
              {selectedNode ? (
                <>
                  <span
                    className="badgeDot"
                    style={{ background: TYPE_COLORS[selectedNode.type], width: 12, height: 12 }}
                  />
                  {selectedNode.label}
                </>
              ) : (
                "🧭 تفاصيل العقدة"
              )}
            </div>
            {!selectedNode && (
              <p style={{ color: "var(--text-2)", margin: 0, fontSize: 14.5 }}>
                انقر على أي عقدة في الشبكة لعرض تفاصيلها وعلاقاتها هنا.
              </p>
            )}
            {selectedNode && (
              <>
                <div className="answerMeta" style={{ margin: "0 0 10px" }}>
                  <span className="chip">{TYPE_LABELS[selectedNode.type] || selectedNode.type}</span>
                  <span className="chip">الوزن: {selectedNode.weight}</span>
                </div>
                {nodeDetail &&
                  Object.entries(nodeDetail.neighbors).map(([type, items]) => (
                    <div key={type} className="neighborGroup">
                      <h4>
                        {TYPE_LABELS[type] || type} ({items.length})
                      </h4>
                      <div className="neighborList">
                        {items.slice(0, 14).map((item) => (
                          <button
                            key={item.id}
                            type="button"
                            className="chip chipBtn"
                            title={item.edge_type}
                            onClick={() => setSelectedId(item.id)}
                          >
                            {item.label}
                          </button>
                        ))}
                        {items.length > 14 && <span className="chip">+{items.length - 14}</span>}
                      </div>
                    </div>
                  ))}
                <button type="button" className="btn btnGhost" onClick={() => setSelectedId(null)}>
                  إلغاء التحديد
                </button>
              </>
            )}
          </div>
        </aside>
      </div>
    </>
  );
}
