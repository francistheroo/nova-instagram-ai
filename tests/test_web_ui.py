from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_content_studio_page_loads(monkeypatch):
    monkeypatch.setenv("NOVA_USER_USERNAME", "test-user")
    monkeypatch.setenv("NOVA_USER_PASSWORD", "test-password")
    response = client.get("/app", auth=("test-user", "test-password"))

    assert response.status_code == 200
    assert "NOVA Content Studio" in response.text
    assert "/ai/generate-caption" in response.text
    assert "/ai/content-ideas" in response.text
    assert "/ai/generate-image" in response.text
    assert "AI image creator" in response.text
    assert "does not publish" in response.text.lower()
