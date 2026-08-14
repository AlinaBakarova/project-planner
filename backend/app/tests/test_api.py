import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Тесты регистрации
def test_register_success():
    response = client.post("/api/auth/register", json={
        "username": "testuser",
        "password": "testpass123"
    })
    assert response.status_code == 200
    assert "token" in response.json()

def test_register_duplicate():
    # Регистрируем первый раз
    client.post("/api/auth/register", json={
        "username": "testuser2",
        "password": "testpass123"
    })
    # Пробуем ещё раз
    response = client.post("/api/auth/register", json={
        "username": "testuser2",
        "password": "testpass123"
    })
    assert response.status_code == 400

# Тесты проектов
def test_create_project():
    # Логинимся
    login_response = client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "testpass123"
    })
    token = login_response.json()["token"]
    
    # Создаём проект
    response = client.post("/api/projects", 
        json={"name": "Test Project"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Test Project"

# Тесты планирования
def test_plan_calculation():
    # Логинимся
    login_response = client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "testpass123"
    })
    token = login_response.json()["token"]
    
    # Создаём проект
    project_response = client.post("/api/projects",
        json={"name": "Plan Test"},
        headers={"Authorization": f"Bearer {token}"}
    )
    project_id = project_response.json()["id"]
    
    # Создаём задачу
    task_response = client.post(f"/api/projects/{project_id}/tasks",
        json={"name": "Task 1", "duration": 60, "dependencies": [], "resource_ids": []},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Запускаем планирование
    plan_response = client.post(f"/api/projects/{project_id}/plan/calculate",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert plan_response.status_code == 200
    assert plan_response.json()["status"] in ["done", "error"]
