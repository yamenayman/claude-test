import pytest

from api.retrieval import resolve_backend, retrieve_local
from api.settings import Settings


def make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_local_backend_is_forced_when_requested():
    assert resolve_backend(make_settings(retrieval_backend="local")) == "local"


def test_local_retrieval_returns_relevant_chunk_for_termination():
    hits = retrieve_local("هل يجوز إنهاء عقد العمل بدون إشعار؟", 3, make_settings())
    assert hits
    assert hits[0]["vector_score"] > 0
    joined = " ".join(h["topic"] + h["reference"] for h in hits)
    assert "إنهاء" in joined or "الإشعار" in joined


def test_local_retrieval_wage_deduction():
    hits = retrieve_local("هل يجوز الخصم من أجر العامل؟", 3, make_settings())
    assert hits
    assert "الأجر" in hits[0]["topic"] or "الخصم" in hits[0]["topic"]


def test_local_retrieval_respects_k():
    hits = retrieve_local("عقد العمل", 5, make_settings())
    assert len(hits) <= 5


def test_local_retrieval_scores_are_normalized():
    hits = retrieve_local("الإجازة السنوية", 10, make_settings())
    assert hits
    assert all(0.0 <= h["vector_score"] <= 1.0 for h in hits)
    # Results are sorted by descending score.
    scores = [h["vector_score"] for h in hits]
    assert scores == sorted(scores, reverse=True)
