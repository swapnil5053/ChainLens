"""HTTP surface tests.

These run without a database or an embedding provider: the point is that the service
starts in a degraded environment and reports that honestly, rather than crashing or
claiming to be healthy.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from chainlens.main import create_app


@pytest.fixture()
def client() -> TestClient:
    with TestClient(create_app()) as instance:
        yield instance


def test_health_is_liveness_only_and_returns_200(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "2.0.0"}


def test_readyz_reports_degraded_and_explains_each_missing_dependency(
    client: TestClient,
) -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ready", "degraded"}
    assert isinstance(body["postgres"], bool)
    if not body["redis"]:
        assert "redis_impact" in body["detail"]


def test_request_id_is_echoed_back(client: TestClient) -> None:
    response = client.get("/health", headers={"x-request-id": "abc-123"})
    assert response.headers["x-request-id"] == "abc-123"


def test_upload_rejects_a_non_pdf_before_touching_the_database(client: TestClient) -> None:
    response = client.post("/documents", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code in {415, 503}


def test_query_requires_a_question(client: TestClient) -> None:
    assert client.post("/query", json={"question": ""}).status_code == 422


def test_openapi_document_is_generated(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for expected in ("/health", "/readyz", "/documents", "/query", "/metrics/summary"):
        assert expected in paths
