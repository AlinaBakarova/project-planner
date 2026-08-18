# Project Planner

Серверный движок интеллектуального планирования задач и ресурсов.

## О проекте

Project Planner — это локально разворачиваемый прототип для планирования задач с учётом:
- Зависимостей между задачами (precedence constraints)
- Ограниченных ресурсов (люди, оборудование, материалы)
- Длительности задач
- Многопользовательской работы

## Запуск

### Требования
- Docker
- Docker Compose (или Docker CLI)

### Запуск через Docker

```bash
docker-compose up -d
```

# Доступ
Frontend: http://localhost:3000

API (Swagger): http://localhost:8000/docs

Health check: http://localhost:8000/health

# Запуск вручную (если Docker Compose не работает)

## Redis
```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine
```
## Backend
```
docker build -t project_backend ./backend
docker run -d \
  --name scheduler-backend \
  -p 8000:8000 \
  -v project_backend-data:/data \
  -e DATABASE_URL=sqlite:////data/app.db \
  -e REDIS_URL=redis://redis:6379/0 \
  -e SECRET_KEY=dev-secret-key-change-in-production \
  --link redis:redis \
  project_backend
```
## Celery Worker
```bash
docker run -d \
  --name celery-worker \
  -v project_backend-data:/data \
  -e DATABASE_URL=sqlite:////data/app.db \
  -e REDIS_URL=redis://redis:6379/0 \
  --link redis:redis \
  project_backend \
  celery -A app.celery_app worker --loglevel=info
```
## Frontend
```bash
docker run -d \
  --name scheduler-frontend \
  -p 3000:80 \
  -v $(pwd)/frontend:/usr/share/nginx/html:ro \
  nginx:alpine
```  
  
 ```bash
┌─────────────────────────────────────────┐
│            Frontend (nginx)             │
│         http://localhost:3000           │
└─────────────────┬───────────────────────┘
                  │ HTTP/REST
┌─────────────────▼───────────────────────┐
│           Backend (FastAPI)             │
│         http://localhost:8000           │
│  • Аутентификация (JWT)                 │
│  • CRUD проектов, задач, ресурсов       │
│  • Запуск планирования                  │
│  • Экспорт CSV/JSON/PDF                 │
└─────────────────┬───────────────────────┘
                  │
      ┌───────────┼───────────┐
      │           │           │
┌─────▼─────┐ ┌───▼─────┐ ┌───▼─────┐
│  SQLite   │ │  Redis  │ │ Celery  │
│ (данные)  │ │(брокер) │ │ Worker  │
└───────────┘ └─────────┘ └─────────┘
``` 
  
 ## Модель планирования
# Задачи
ID — уникальный идентификатор

Название

Длительность — в минутах

Зависимости — задача B не может начаться до завершения задачи A

Ресурсы — список ресурсов с указанием количества

#  Ресурсы
Типы:

human (человек) — возобновляемый, после задачи освобождается

machine (оборудование) — возобновляемый, после задачи освобождается

material (материал) — расходуемый, количество уменьшается

Алгоритм планирования
Жадный алгоритм (list scheduling)

Задачи сортируются по длительности (сначала короткие)

Назначение происходит при первой доступности ресурсов

Учитываются зависимости и ограничения ресурсов

# Ограничения
Нельзя удалить ресурс, если он используется в задачах

Нельзя создать задачу, если запрошено больше ресурса, чем доступно

Циклические зависимости отклоняются

# Функциональность
✅ Регистрация и авторизация (JWT)

✅ Изоляция пользовательских данных

✅ CRUD проектов, задач, ресурсов

✅ Планирование с ограничениями

✅ Асинхронный пересчёт (Celery)

✅ Автоматический пересчёт при изменениях

✅ Экспорт: CSV, JSON, PDF (скриншот диаграммы)

✅ Импорт: JSON, CSV

✅ Диаграмма Ганта

✅ Граф конфликтов при невозможности построить план

✅ Документация в интерфейсе

Тестирование
```bash
docker exec -it scheduler-backend bash -c "cd /app && pip install pytest httpx==0.24.1 && PYTHONPATH=/app pytest tests/ -v"
```

Перезапуск сервисов
```bash
docker restart redis scheduler-backend celery-worker scheduler-frontend
```
Логи
```bash
# Backend
docker logs scheduler-backend

# Celery Worker
docker logs celery-worker

# Файл логов
docker exec scheduler-backend cat /data/logs/app.log
```

