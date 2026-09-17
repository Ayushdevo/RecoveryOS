from fastapi.testclient import TestClient

from apps.backend.main import app


def test_health_endpoint_reports_healthy():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
