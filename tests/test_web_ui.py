from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_content_studio_page_loads():
    response = client.get("/app")

    assert response.status_code == 200
    assert "NOVA Content Studio" in response.text
    assert "/ai/generate-caption" in response.text
    assert "/ai/content-ideas" in response.text
    assert "does not publish" in response.text.lower()
    assert "Connection checklist" in response.text
    assert "/integrations/status" in response.text
