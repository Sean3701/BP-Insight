from fastapi.testclient import TestClient
from backend.main import app

def test_workspace_assets_are_not_stored_between_releases():
    with TestClient(app) as client:
        for path in ['/app/', '/app/app.js', '/app/style.css']:
            response=client.get(path)
            assert response.status_code==200
            assert response.headers.get('cache-control')=='no-store'
