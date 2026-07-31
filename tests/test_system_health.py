from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_check_and_security_headers() -> None:
    response = client.get("/api/v1/system/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-request-id"]
