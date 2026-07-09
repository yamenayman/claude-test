from api.corpus import extract_article_numbers
from api.kg import KnowledgeGraph, detect_concepts, get_knowledge_graph


SAMPLE_CHUNKS = [
    {
        "chunk_id": "law_art_23",
        "source_type": "official_law_selected",
        "source_name": "قانون العمل الأردني",
        "reference": "قانون العمل الأردني رقم 8 لسنة 1996 وتعديلاته، المادة 23",
        "topic": "إنهاء عقد العمل",
        "text": "يجوز إنهاء عقد العمل غير محدد المدة بعد إشعار خطي قبل شهر على الأقل.",
    },
    {
        "chunk_id": "guide_p10",
        "source_type": "explainer_guide",
        "source_name": "دليل قانون العمل",
        "reference": "دليل حول قانون العمل الأردني، صفحة 10",
        "topic": "الفصل التعسفي",
        "text": "إذا فصل العامل فصلاً تعسفياً دون إشعار فله المطالبة بالتعويض عن إنهاء عقد العمل.",
    },
]


def test_extract_article_numbers_from_reference():
    assert extract_article_numbers("قانون العمل الأردني رقم 8 لسنة 1996 وتعديلاته، المادة 23") == [23]


def test_extract_article_numbers_ignores_law_number():
    numbers = extract_article_numbers("قانون العمل الأردني رقم 8 لسنة 1996 وتعديلاته")
    assert 8 not in numbers
    assert numbers == []


def test_detect_concepts_matches_with_attached_particles():
    assert "unfair_dismissal" in detect_concepts("ما المقصود بالفصل التعسفي؟")
    assert "termination" in detect_concepts("هل يجوز إنهاء عقد العمل بدون إشعار؟")


def test_detect_concepts_does_not_match_inside_words():
    # "تأجير" contains the normalized letters of "أجر" but is not about wages.
    assert "wage" not in detect_concepts("عقد تأجير المعدات")


def test_build_graph_from_sample_chunks():
    graph = KnowledgeGraph.build(SAMPLE_CHUNKS)
    stats = graph.stats()
    assert stats["node_types"]["chunk"] == 2
    assert stats["node_types"]["article"] == 1
    assert "article:23" in graph.nodes
    assert graph.chunk_articles["law_art_23"] == [23]
    assert "termination" in graph.chunk_concepts["law_art_23"]

    node = graph.get_node("article:23")
    assert node is not None
    assert any(item["type"] == "chunk" for group in node["neighbors"].values() for item in group)


def test_related_concepts_projection():
    graph = KnowledgeGraph.build(SAMPLE_CHUNKS)
    related = graph.related_concepts(["termination"])
    labels = {item["label"] for item in related}
    assert "الإشعار" in labels


def test_full_corpus_graph_builds():
    graph = get_knowledge_graph()
    stats = graph.stats()
    assert stats["node_types"]["chunk"] > 0
    assert stats["node_types"]["article"] > 0
    assert stats["node_types"]["concept"] > 0
    assert stats["edges"] > stats["nodes"]


def test_subgraph_excludes_chunks_by_default():
    graph = get_knowledge_graph()
    subgraph = graph.subgraph()
    assert all(node["type"] != "chunk" for node in subgraph["nodes"])
    node_ids = {node["id"] for node in subgraph["nodes"]}
    for edge in subgraph["edges"]:
        assert edge["source"] in node_ids and edge["target"] in node_ids
