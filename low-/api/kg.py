"""Knowledge graph over the Jordanian labor-law corpus.

The graph is derived deterministically from the seeded legal chunks at
startup. The law texts themselves are never modified: extraction is rule
based (article references, topics, and a curated Arabic concept lexicon), so
the graph always stays in sync with the corpus.

Node types:
    - ``source``:  a law or guide document
    - ``article``: an article of the Jordanian Labor Law No. 8 of 1996
    - ``topic``:   the curated topic attached to each chunk
    - ``concept``: a labor-law concept from the lexicon below
    - ``chunk``:   one legal text chunk

Edge types:
    - chunk  -> source  : ``belongs_to``
    - chunk  -> article : ``cites``
    - chunk  -> topic   : ``about``
    - chunk  -> concept : ``mentions``
    - article-> source  : ``part_of``
    - concept<->concept : ``related_to``   (co-occurrence, projected)
    - article<->concept : ``covers``       (projected through chunks)
    - topic  <->concept : ``discusses``    (projected through chunks)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Iterable

from api.corpus import extract_article_numbers, get_corpus_chunks
from api.text_normalize import normalize_arabic_text

# Curated lexicon of Jordanian labor-law concepts. Aliases are matched against
# normalized text (see text_normalize) as whole words, so short aliases do not
# match inside longer unrelated words.
CONCEPT_LEXICON: dict[str, dict[str, Any]] = {
    "employment_contract": {"label": "عقد العمل", "aliases": ["عقد العمل", "عقود العمل", "بعقد العمل", "لعقد العمل"]},
    "fixed_term_contract": {"label": "العقد محدد المدة", "aliases": ["محدد المده", "محدده المده", "لمده محدوده"]},
    "wage": {"label": "الأجر", "aliases": ["الاجر", "اجر", "الاجور", "اجور", "بالاجر", "اجره"]},
    "minimum_wage": {"label": "الحد الأدنى للأجور", "aliases": ["الحد الادني للاجور", "الحد الادني للاجر"]},
    "annual_leave": {"label": "الإجازة السنوية", "aliases": ["الاجازه السنويه", "اجازه سنويه", "الاجازات السنويه"]},
    "sick_leave": {"label": "الإجازة المرضية", "aliases": ["الاجازه المرضيه", "اجازه مرضيه", "الاجازات المرضيه"]},
    "maternity_leave": {"label": "إجازة الأمومة", "aliases": ["اجازه الامومه", "اجازه امومه"]},
    "nursing_break": {"label": "ساعة الرضاعة", "aliases": ["الرضاعه", "لارضاع"]},
    "unfair_dismissal": {"label": "الفصل التعسفي", "aliases": ["الفصل التعسفي", "فصلا تعسفيا", "فصل تعسفي"]},
    "notice": {"label": "الإشعار", "aliases": ["الاشعار", "اشعار", "باشعار", "الانذار"]},
    "overtime": {"label": "العمل الإضافي", "aliases": ["العمل الاضافي", "عمل اضافي", "ساعات اضافيه", "الاضافي"]},
    "working_hours": {"label": "ساعات العمل", "aliases": ["ساعات العمل", "ساعه عمل", "ساعات عمل"]},
    "flexible_work": {"label": "العمل المرن", "aliases": ["العمل المرن", "عمل مرن"]},
    "weekly_rest": {"label": "العطلة الأسبوعية", "aliases": ["العطله الاسبوعيه", "عطله اسبوعيه", "يوم العطله"]},
    "public_holidays": {"label": "الأعياد والعطل الرسمية", "aliases": ["العطل الرسميه", "الاعياد الدينيه", "الاعياد الرسميه", "العطل الدينيه"]},
    "termination": {"label": "إنهاء عقد العمل", "aliases": ["انهاء عقد العمل", "انهاء العقد", "انهاء خدمه", "انهاء الخدمه", "انهاء عمل", "انهاء العمل", "بانهاء"]},
    "abandonment": {"label": "ترك العمل دون إشعار", "aliases": ["ترك العمل", "يترك العمل", "ترك عمله"]},
    "economic_reasons": {"label": "الأسباب الاقتصادية والفنية", "aliases": ["اسباب اقتصاديه", "الاسباب الاقتصاديه", "اقتصاديه او فنيه"]},
    "wage_deduction": {"label": "الخصم من الأجر", "aliases": ["الخصم من الاجر", "الحسم من الاجر", "الاقتطاع", "الاقتطاعات", "اقتطاع", "حسم", "الحسم", "الخصم", "خصم"]},
    "fines": {"label": "الغرامات", "aliases": ["الغرامات", "غرامه", "الغرامه", "غرامات"]},
    "service_certificate": {"label": "شهادة الخدمة", "aliases": ["شهاده الخدمه", "شهاده خدمه"]},
    "end_of_service": {"label": "مكافأة نهاية الخدمة", "aliases": ["مكافاه نهايه الخدمه", "نهايه الخدمه"]},
    "probation": {"label": "فترة التجربة", "aliases": ["التجربه", "تحت التجربه", "فتره التجربه"]},
    "juvenile_labor": {"label": "عمل الأحداث", "aliases": ["الحدث", "الاحداث", "حدثا"]},
    "employer": {"label": "صاحب العمل", "aliases": ["صاحب العمل", "اصحاب العمل", "لصاحب العمل"]},
    "union": {"label": "النقابة", "aliases": ["النقابه", "نقابه العمال", "نقابه"]},
    "internal_regulations": {"label": "الأنظمة الداخلية", "aliases": ["الانظمه الداخليه", "النظام الداخلي"]},
    "disciplinary_measures": {"label": "الإجراءات التأديبية", "aliases": ["التاديبيه", "تاديبي", "عقوبه"]},
    "acquired_rights": {"label": "الحقوق المكتسبة", "aliases": ["الحقوق المكتسبه", "حق مكتسب", "التنازل عن اي حق"]},
    "minimum_working_age": {"label": "الحد الأدنى لسن العمل", "aliases": ["سن العمل", "السادسه عشره", "الثامنه عشره", "السابعه"]},
    "labor_inspector": {"label": "مفتش العمل", "aliases": ["مفتش العمل", "مفتشو العمل", "التفتيش"]},
    "vocational_training": {"label": "التدريب المهني", "aliases": ["التدريب المهني", "التلمذه المهنيه", "التاهيل"]},
}

LAW_SOURCE_TYPES = {"official_law_selected"}


@dataclass
class KGNode:
    id: str
    type: str
    label: str
    weight: int = 0
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "type": self.type, "label": self.label, "weight": self.weight, **self.meta}


@dataclass
class KGEdge:
    source: str
    target: str
    type: str
    weight: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "target": self.target, "type": self.type, "weight": self.weight}


def _word_boundary_pattern(alias: str) -> re.Pattern[str]:
    # Python's \w matches Arabic letters but not Arabic punctuation ("؟"),
    # which unlike letters must count as a word boundary. Attached particles
    # (و، ف، ب، ك) before the term are allowed: "بالفصل التعسفي" == "الفصل التعسفي".
    escaped = re.escape(normalize_arabic_text(alias))
    return re.compile(rf"(?<!\w)[وف]?[بك]?{escaped}(?!\w)")


@lru_cache(maxsize=1)
def _compiled_lexicon() -> dict[str, list[re.Pattern[str]]]:
    return {
        concept_id: [_word_boundary_pattern(alias) for alias in entry["aliases"]]
        for concept_id, entry in CONCEPT_LEXICON.items()
    }


def detect_concepts(text: str) -> list[str]:
    """Return the lexicon concept ids mentioned in the given Arabic text."""
    normalized = normalize_arabic_text(text or "")
    if not normalized:
        return []
    found: list[str] = []
    for concept_id, patterns in _compiled_lexicon().items():
        if any(pattern.search(normalized) for pattern in patterns):
            found.append(concept_id)
    return found


class KnowledgeGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, KGNode] = {}
        self.edges: list[KGEdge] = []
        self._edge_keys: dict[tuple[str, str, str], int] = {}
        self.adjacency: dict[str, set[int]] = {}
        self.chunk_concepts: dict[str, list[str]] = {}
        self.chunk_articles: dict[str, list[int]] = {}

    # -- construction -----------------------------------------------------

    def _add_node(self, node_id: str, node_type: str, label: str, **meta: Any) -> KGNode:
        node = self.nodes.get(node_id)
        if node is None:
            node = KGNode(id=node_id, type=node_type, label=label, meta=dict(meta))
            self.nodes[node_id] = node
            self.adjacency[node_id] = set()
        return node

    def _add_edge(self, source: str, target: str, edge_type: str, weight: int = 1) -> None:
        if source == target or source not in self.nodes or target not in self.nodes:
            return
        key = (source, target, edge_type)
        reverse_key = (target, source, edge_type)
        index = self._edge_keys.get(key)
        if index is None and edge_type in {"related_to", "covers", "discusses"}:
            index = self._edge_keys.get(reverse_key)
        if index is not None:
            self.edges[index].weight += weight
            return
        edge = KGEdge(source=source, target=target, type=edge_type, weight=weight)
        self.edges.append(edge)
        index = len(self.edges) - 1
        self._edge_keys[key] = index
        self.adjacency[source].add(index)
        self.adjacency[target].add(index)

    @classmethod
    def build(cls, chunks: Iterable[dict[str, Any]]) -> "KnowledgeGraph":
        graph = cls()
        for chunk in chunks:
            chunk_id = str(chunk.get("chunk_id") or "")
            if not chunk_id:
                continue
            text = str(chunk.get("text") or "")
            topic = str(chunk.get("topic") or "").strip()
            reference = str(chunk.get("reference") or "")
            source_name = str(chunk.get("source_name") or "").strip()
            source_type = str(chunk.get("source_type") or "").strip()

            chunk_node_id = f"chunk:{chunk_id}"
            graph._add_node(
                chunk_node_id,
                "chunk",
                topic or chunk_id,
                chunk_id=chunk_id,
                reference=reference,
                source_type=source_type,
                preview=text[:180],
            )

            source_id = None
            if source_name:
                source_id = f"source:{source_name}"
                node = graph._add_node(source_id, "source", source_name, source_type=source_type)
                node.weight += 1
                graph._add_edge(chunk_node_id, source_id, "belongs_to")

            topic_id = None
            if topic:
                topic_id = f"topic:{topic}"
                node = graph._add_node(topic_id, "topic", topic)
                node.weight += 1
                graph._add_edge(chunk_node_id, topic_id, "about")

            articles = extract_article_numbers(reference, text if source_type in LAW_SOURCE_TYPES else None)
            graph.chunk_articles[chunk_id] = articles
            article_ids: list[str] = []
            for number in articles:
                article_id = f"article:{number}"
                node = graph._add_node(article_id, "article", f"المادة {number}", number=number)
                node.weight += 1
                article_ids.append(article_id)
                graph._add_edge(chunk_node_id, article_id, "cites")
                if source_id and source_type in LAW_SOURCE_TYPES:
                    graph._add_edge(article_id, source_id, "part_of")

            concepts = detect_concepts(text)
            graph.chunk_concepts[chunk_id] = concepts
            concept_ids: list[str] = []
            for concept_id in concepts:
                node_id = f"concept:{concept_id}"
                node = graph._add_node(node_id, "concept", CONCEPT_LEXICON[concept_id]["label"], key=concept_id)
                node.weight += 1
                concept_ids.append(node_id)
                graph._add_edge(chunk_node_id, node_id, "mentions")

            # Projected edges (concept co-occurrence, article/topic coverage)
            for i, left in enumerate(concept_ids):
                for right in concept_ids[i + 1 :]:
                    graph._add_edge(left, right, "related_to")
                for article_id in article_ids:
                    graph._add_edge(article_id, left, "covers")
                if topic_id:
                    graph._add_edge(topic_id, left, "discusses")
        return graph

    # -- queries -----------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        node_counts: dict[str, int] = {}
        for node in self.nodes.values():
            node_counts[node.type] = node_counts.get(node.type, 0) + 1
        edge_counts: dict[str, int] = {}
        for edge in self.edges:
            edge_counts[edge.type] = edge_counts.get(edge.type, 0) + 1
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "node_types": node_counts,
            "edge_types": edge_counts,
        }

    def subgraph(self, node_types: set[str] | None = None, limit: int = 400) -> dict[str, Any]:
        types = node_types or {"concept", "article", "topic", "source"}
        selected = [node for node in self.nodes.values() if node.type in types]
        selected.sort(key=lambda node: node.weight, reverse=True)
        selected = selected[:limit]
        selected_ids = {node.id for node in selected}
        edges = [
            edge.to_dict()
            for edge in self.edges
            if edge.source in selected_ids and edge.target in selected_ids
        ]
        return {"nodes": [node.to_dict() for node in selected], "edges": edges}

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        node = self.nodes.get(node_id)
        if node is None:
            return None
        neighbors: dict[str, list[dict[str, Any]]] = {}
        for index in sorted(self.adjacency.get(node_id, set())):
            edge = self.edges[index]
            other_id = edge.target if edge.source == node_id else edge.source
            other = self.nodes.get(other_id)
            if other is None:
                continue
            entry = {**other.to_dict(), "edge_type": edge.type, "edge_weight": edge.weight}
            neighbors.setdefault(other.type, []).append(entry)
        for group in neighbors.values():
            group.sort(key=lambda item: item["edge_weight"], reverse=True)
        return {"node": node.to_dict(), "neighbors": neighbors}

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        normalized = normalize_arabic_text(query or "")
        if not normalized:
            return []
        matches = [
            node.to_dict()
            for node in self.nodes.values()
            if normalized in normalize_arabic_text(node.label)
        ]
        matches.sort(key=lambda item: item["weight"], reverse=True)
        return matches[:limit]

    def concept_list(self) -> list[dict[str, Any]]:
        items = []
        for concept_id, entry in CONCEPT_LEXICON.items():
            node = self.nodes.get(f"concept:{concept_id}")
            items.append(
                {
                    "id": f"concept:{concept_id}",
                    "key": concept_id,
                    "label": entry["label"],
                    "chunks": node.weight if node else 0,
                }
            )
        items.sort(key=lambda item: item["chunks"], reverse=True)
        return items

    def related_concepts(self, concept_ids: list[str], limit: int = 6) -> list[dict[str, Any]]:
        """Concepts connected by ``related_to`` edges to any of the given ids."""
        wanted = {f"concept:{cid}" if not cid.startswith("concept:") else cid for cid in concept_ids}
        scores: dict[str, int] = {}
        for node_id in wanted:
            for index in self.adjacency.get(node_id, set()):
                edge = self.edges[index]
                if edge.type != "related_to":
                    continue
                other = edge.target if edge.source == node_id else edge.source
                if other in wanted:
                    continue
                scores[other] = scores.get(other, 0) + edge.weight
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]
        return [
            {**self.nodes[node_id].to_dict(), "strength": strength}
            for node_id, strength in ranked
            if node_id in self.nodes
        ]


@lru_cache(maxsize=1)
def get_knowledge_graph() -> KnowledgeGraph:
    return KnowledgeGraph.build(get_corpus_chunks())
