from app import create_app


def test_health_endpoint():
    app = create_app({"TESTING": True, "SECRET_KEY": "test"})
    response = app.test_client().get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}

