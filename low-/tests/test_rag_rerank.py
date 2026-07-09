from api.rag import rerank_chunks


def test_kg_boost_promotes_concept_matching_chunk():
    question = "هل يجوز إنهاء عقد العمل بدون إشعار؟"
    chunks = [
        {
            "chunk_id": "generic",
            "topic": "موضوع عام",
            "reference": "مرجع",
            "text": "نص عام لا يتعلق بالسؤال إطلاقاً.",
            "vector_score": 0.80,
        },
        {
            "chunk_id": "relevant",
            "topic": "موضوع عام",
            "reference": "مرجع",
            "text": "إنهاء عقد العمل يتطلب إشعاراً خطياً.",
            "vector_score": 0.80,
        },
    ]

    reranked = rerank_chunks(
        question,
        chunks,
        question_concepts=["employment_contract", "termination", "notice"],
        kg_boost_per_concept=0.04,
    )

    assert reranked[0]["chunk_id"] == "relevant"
    assert reranked[0]["kg_concepts"]
    assert reranked[0]["score"] > reranked[1]["score"]


def test_rerank_without_concepts_matches_legacy_behavior():
    chunks = [
        {"chunk_id": "a", "topic": "", "reference": "", "text": "نص", "vector_score": 0.5},
    ]
    reranked = rerank_chunks("سؤال", chunks, question_concepts=[])

    assert reranked[0]["kg_concepts"] == []
    assert reranked[0]["score"] == 0.5
