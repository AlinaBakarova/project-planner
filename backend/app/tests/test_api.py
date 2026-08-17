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


import sys
import os
sys.path.insert(0, '/app')

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# ============================================
# ФИКСТУРЫ
# ============================================

@pytest.fixture
def registered_user():
    """Создаёт и возвращает пользователя."""
    import uuid
    username = f"testuser_{uuid.uuid4().hex[:8]}"
    password = "testpass123"
    
    response = client.post("/api/auth/register", json={
        "username": username,
        "password": password
    })
    assert response.status_code == 200
    token = response.json()["token"]
    
    return {"username": username, "password": password, "token": token}


@pytest.fixture
def auth_headers(registered_user):
    """Возвращает заголовки с токеном."""
    return {"Authorization": f"Bearer {registered_user['token']}"}


@pytest.fixture
def created_project(auth_headers):
    """Создаёт проект и возвращает его ID."""
    response = client.post("/api/projects", 
        json={"name": "Test Project"},
        headers=auth_headers
    )
    assert response.status_code == 200
    return response.json()


# ============================================
# ТЕСТЫ АУТЕНТИФИКАЦИИ
# ============================================

class TestAuth:
    
    def test_register_success(self):
        """Успешная регистрация нового пользователя."""
        import uuid
        username = f"newuser_{uuid.uuid4().hex[:8]}"
        
        response = client.post("/api/auth/register", json={
            "username": username,
            "password": "password123"
        })
        
        assert response.status_code == 200
        assert "token" in response.json()
        assert len(response.json()["token"]) > 0
    
    def test_register_duplicate(self, registered_user):
        """Регистрация с уже существующим именем."""
        response = client.post("/api/auth/register", json={
            "username": registered_user["username"],
            "password": "password123"
        })
        
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
    
    def test_login_success(self, registered_user):
        """Успешный вход с правильными данными."""
        response = client.post("/api/auth/login", json={
            "username": registered_user["username"],
            "password": registered_user["password"]
        })
        
        assert response.status_code == 200
        assert "token" in response.json()
    
    def test_login_wrong_password(self, registered_user):
        """Вход с неправильным паролем."""
        response = client.post("/api/auth/login", json={
            "username": registered_user["username"],
            "password": "wrongpassword"
        })
        
        assert response.status_code == 401
    
    def test_login_nonexistent_user(self):
        """Вход с несуществующим пользователем."""
        response = client.post("/api/auth/login", json={
            "username": "nonexistent_user_12345",
            "password": "password123"
        })
        
        assert response.status_code == 401


# ============================================
# ТЕСТЫ ПРОЕКТОВ
# ============================================

class TestProjects:
    
    def test_create_project(self, auth_headers):
        """Создание проекта."""
        response = client.post("/api/projects",
            json={"name": "My Project"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["name"] == "My Project"
        assert "id" in response.json()
    
    def test_list_projects(self, auth_headers, created_project):
        """Получение списка проектов."""
        response = client.get("/api/projects", headers=auth_headers)
        
        assert response.status_code == 200
        projects = response.json()["projects"]
        assert len(projects) >= 1
        assert any(p["id"] == created_project["id"] for p in projects)
    
    def test_get_project(self, auth_headers, created_project):
        """Получение конкретного проекта."""
        response = client.get(f"/api/projects/{created_project['id']}", 
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["id"] == created_project["id"]
    
    def test_get_nonexistent_project(self, auth_headers):
        """Получение несуществующего проекта."""
        response = client.get("/api/projects/99999", headers=auth_headers)
        
        assert response.status_code == 404
    
    def test_user_isolation(self, auth_headers):
        """Пользователь не видит чужие проекты."""
        # Создаём второго пользователя
        import uuid
        username2 = f"isolation_{uuid.uuid4().hex[:8]}"
        response2 = client.post("/api/auth/register", json={
            "username": username2,
            "password": "password123"
        })
        token2 = response2.json()["token"]
        headers2 = {"Authorization": f"Bearer {token2}"}
        
        # Второй пользователь создаёт проект
        client.post("/api/projects",
            json={"name": "User2 Project"},
            headers=headers2
        )
        
        # Первый пользователь не должен видеть проекты второго
        response = client.get("/api/projects", headers=auth_headers)
        projects = response.json()["projects"]
        
        assert all(p["name"] != "User2 Project" for p in projects)


# ============================================
# ТЕСТЫ ЗАДАЧ
# ============================================

class TestTasks:
    
    def test_create_task(self, auth_headers, created_project):
        """Создание задачи."""
        response = client.post(
            f"/api/projects/{created_project['id']}/tasks",
            json={
                "name": "Task 1",
                "duration": 60,
                "dependencies": [],
                "resource_ids": []
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["name"] == "Task 1"
        assert response.json()["duration"] == 60
    
    def test_create_task_with_dependencies(self, auth_headers, created_project):
        """Создание задачи с зависимостями."""
        # Создаём первую задачу
        task1 = client.post(
            f"/api/projects/{created_project['id']}/tasks",
            json={"name": "Task A", "duration": 30, "dependencies": [], "resource_ids": []},
            headers=auth_headers
        ).json()
        
        # Создаём вторую задачу, зависящую от первой
        task2 = client.post(
            f"/api/projects/{created_project['id']}/tasks",
            json={"name": "Task B", "duration": 45, "dependencies": [task1["id"]], "resource_ids": []},
            headers=auth_headers
        ).json()
        
        assert task2["dependencies"] == [task1["id"]]
    
    def test_update_task(self, auth_headers, created_project):
        """Обновление задачи."""
        task = client.post(
            f"/api/projects/{created_project['id']}/tasks",
            json={"name": "Task to Update", "duration": 60, "dependencies": [], "resource_ids": []},
            headers=auth_headers
        ).json()
        
        response = client.put(
            f"/api/tasks/{task['id']}",
            json={"name": "Updated Task", "duration": 120},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Task"
        assert response.json()["duration"] == 120
    
    def test_delete_task(self, auth_headers, created_project):
        """Удаление задачи."""
        task = client.post(
            f"/api/projects/{created_project['id']}/tasks",
            json={"name": "Task to Delete", "duration": 60, "dependencies": [], "resource_ids": []},
            headers=auth_headers
        ).json()
        
        response = client.delete(f"/api/tasks/{task['id']}", headers=auth_headers)
        
        assert response.status_code == 200
        assert "deleted" in response.json()["message"].lower()
    
    def test_create_task_nonexistent_dependency(self, auth_headers, created_project):
        """Создание задачи с несуществующей зависимостью."""
        response = client.post(
            f"/api/projects/{created_project['id']}/tasks",
            json={"name": "Bad Task", "duration": 60, "dependencies": [99999], "resource_ids": []},
            headers=auth_headers
        )
        
        assert response.status_code == 400


# ============================================
# ТЕСТЫ РЕСУРСОВ
# ============================================

class TestResources:
    
    def test_create_resource(self, auth_headers, created_project):
        """Создание ресурса."""
        response = client.post(
            f"/api/projects/{created_project['id']}/resources",
            json={"name": "Developer", "type": "human", "availability": 2},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["name"] == "Developer"
        assert response.json()["availability"] == 2
    
    def test_update_resource(self, auth_headers, created_project):
        """Обновление ресурса."""
        resource = client.post(
            f"/api/projects/{created_project['id']}/resources",
            json={"name": "Machine", "type": "equipment", "availability": 1},
            headers=auth_headers
        ).json()
        
        response = client.put(
            f"/api/resources/{resource['id']}",
            json={"availability": 3},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["availability"] == 3
    
    def test_delete_resource(self, auth_headers, created_project):
        """Удаление ресурса."""
        resource = client.post(
            f"/api/projects/{created_project['id']}/resources",
            json={"name": "Temp", "type": "other", "availability": 1},
            headers=auth_headers
        ).json()
        
        response = client.delete(f"/api/resources/{resource['id']}", headers=auth_headers)
        
        assert response.status_code == 200


# ============================================
# ТЕСТЫ ПЛАНИРОВАНИЯ
# ============================================

class TestPlanning:
    
    def test_calculate_simple_plan(self, auth_headers, created_project):
        """Построение плана для простого проекта."""
        # Создаём задачи
        client.post(
            f"/api/projects/{created_project['id']}/tasks",
            json={"name": "Task 1", "duration": 30, "dependencies": [], "resource_ids": []},
            headers=auth_headers
        )
        client.post(
            f"/api/projects/{created_project['id']}/tasks",
            json={"name": "Task 2", "duration": 45, "dependencies": [], "resource_ids": []},
            headers=auth_headers
        )
        
        # Запускаем планирование
        response = client.post(
            f"/api/projects/{created_project['id']}/plan/calculate",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.json()["status"] in ["pending", "calculating", "done"]
    
    def test_calculate_plan_with_dependencies(self, auth_headers, created_project):
        """Построение плана с зависимостями."""
        # Задача A
        task_a = client.post(
            f"/api/projects/{created_project['id']}/tasks",
            json={"name": "A", "duration": 30, "dependencies": [], "resource_ids": []},
            headers=auth_headers
        ).json()
        
        # Задача B зависит от A
        client.post(
            f"/api/projects/{created_project['id']}/tasks",
            json={"name": "B", "duration": 45, "dependencies": [task_a["id"]], "resource_ids": []},
            headers=auth_headers
        )
        
        # Запускаем планирование
        response = client.post(
            f"/api/projects/{created_project['id']}/plan/calculate",
            headers=auth_headers
        )
        
        assert response.status_code == 200
    
    def test_get_latest_plan(self, auth_headers, created_project):
        """Получение последнего плана."""
        # Создаём задачу
        client.post(
            f"/api/projects/{created_project['id']}/tasks",
            json={"name": "Task", "duration": 30, "dependencies": [], "resource_ids": []},
            headers=auth_headers
        )
        
        # Запускаем планирование
        client.post(
            f"/api/projects/{created_project['id']}/plan/calculate",
            headers=auth_headers
        )
        
        # Получаем план
        response = client.get(
            f"/api/projects/{created_project['id']}/plan/latest",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert "status" in response.json()
    
    def test_no_plan_for_empty_project(self, auth_headers, created_project):
        """План для пустого проекта."""
        response = client.get(
            f"/api/projects/{created_project['id']}/plan/latest",
            headers=auth_headers
        )
        
        assert response.status_code == 404


# ============================================
# ТЕСТЫ ЗДОРОВЬЯ
# ============================================

class TestHealth:
    
    def test_health_check(self):
        """Проверка health check."""
        response = client.get("/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


# ============================================
# ЗАПУСК
# ============================================

if __name__ == "__main__":
    pytest.main(["-v"])
    
