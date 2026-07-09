def test_llm_providers_endpoint(client, monkeypatch):
    monkeypatch.setattr("api.providers.check_ollama_reachable", lambda settings: True)

    response = client.get("/llm/providers")

    assert response.status_code == 200
    payload = response.json()
    assert payload["active"] == "ollama"
    ids = {item["id"] for item in payload["providers"]}
    assert ids == {"ollama", "openai", "anthropic"}


def test_kg_overview_endpoint(client):
    response = client.get("/kg/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["nodes"] > 0
    assert payload["edges"] > 0
    assert "concept" in payload["node_types"]


def test_kg_graph_endpoint_filters_types(client):
    response = client.get("/kg/graph", params={"types": "concept,article", "limit": 50})

    assert response.status_code == 200
    payload = response.json()
    assert payload["nodes"]
    assert all(node["type"] in {"concept", "article"} for node in payload["nodes"])


def test_kg_graph_endpoint_rejects_unknown_type(client):
    response = client.get("/kg/graph", params={"types": "banana"})

    assert response.status_code == 422


def test_kg_node_endpoint(client):
    response = client.get("/kg/node/concept:unfair_dismissal")

    assert response.status_code == 200
    payload = response.json()
    assert payload["node"]["type"] == "concept"
    assert payload["neighbors"]


def test_kg_node_endpoint_404(client):
    response = client.get("/kg/node/concept:not_a_thing")

    assert response.status_code == 404


def test_kg_search_endpoint(client):
    response = client.get("/kg/search", params={"q": "الفصل"})

    assert response.status_code == 200
    assert response.json()["results"]


def test_corpus_chunks_endpoint(client):
    response = client.get("/corpus/chunks", params={"limit": 5})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] > 0
    assert len(payload["items"]) == 5
    first = payload["items"][0]
    assert first["chunk_id"]
    assert first["text"]


def test_corpus_chunks_filter_by_query(client):
    response = client.get("/corpus/chunks", params={"q": "الفصل التعسفي", "limit": 50})

    assert response.status_code == 200
    payload = response.json()
    assert 0 < payload["total"] < 73


def test_corpus_topics_endpoint(client):
    response = client.get("/corpus/topics")

    assert response.status_code == 200
    topics = response.json()
    assert topics
    assert all(item["count"] >= 1 for item in topics)


def test_rag_answer_rejects_unknown_provider(client):
    response = client.post("/rag/answer", json={"question": "سؤال تجريبي", "provider": "banana"})

    assert response.status_code == 422
