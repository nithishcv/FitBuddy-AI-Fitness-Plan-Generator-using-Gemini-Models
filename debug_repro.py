from fastapi.testclient import TestClient
from app.main import app

payload = {
    'user_id': 'testuser123',
    'name': 'Alice Example',
    'age': 30,
    'weight': 70,
    'goal': 'general wellness',
    'intensity': 'medium',
}

with TestClient(app) as client:
    response = client.post('/generate-workout', data=payload)
    print('STATUS', response.status_code)
    print(response.text[:2000])
