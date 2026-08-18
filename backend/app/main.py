from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
from logging.handlers import RotatingFileHandler
import os
import csv
import io

from . import models, schemas, auth
from .database import engine, SessionLocal
from .planner import run_planning_algorithm

# Logging configuration
LOG_DIR = "/data/logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(
            f"{LOG_DIR}/app.log",
            maxBytes=10*1024*1024,
            backupCount=5
        )
    ]
)
logger = logging.getLogger(__name__)

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Project Management API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def trigger_auto_recalc(project_id: int, db: Session):
    """
    Automatically trigger plan recalculation when tasks or resources change.
    """
    tasks_count = db.query(models.Task).filter(
        models.Task.project_id == project_id
    ).count()
    
    if tasks_count == 0:
        logger.info(f"No tasks for project {project_id}, skipping auto-recalc")
        return None
    
    new_plan = models.Plan(
        project_id=project_id,
        status="pending",
        data=None
    )
    db.add(new_plan)
    db.commit()
    db.refresh(new_plan)
    
    try:
        from .tasks import calculate_plan_task
        task = calculate_plan_task.delay(new_plan.id)
        logger.info(f"Auto-recalculation task {task.id} started for project {project_id}")
    except Exception as e:
        logger.error(f"Failed to trigger auto-recalc: {e}")
    
    return new_plan.id

# Auth endpoints
@app.post("/api/auth/register", response_model=schemas.TokenResponse)
def register(user: schemas.UserRegister, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = auth.hash_password(user.password)
    db_user = models.User(username=user.username, password_hash=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    token = auth.create_access_token(
        data={"sub": str(db_user.id), "username": db_user.username}
    )
    return {"token": token}


@app.post("/api/auth/login", response_model=schemas.TokenResponse)
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if not db_user or not auth.verify_password(user.password, db_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    token = auth.create_access_token(
        data={"sub": str(db_user.id), "username": db_user.username}
    )
    return {"token": token}

# Project endpoints
@app.post("/api/projects", response_model=schemas.ProjectResponse)
def create_project(
    project: schemas.ProjectCreate,
    current_user: dict = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    db_project = models.Project(name=project.name, user_id=current_user["id"])
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return {"id": db_project.id, "name": db_project.name}

@app.get("/api/projects", response_model=schemas.ProjectListResponse)
def list_projects(
    current_user: dict = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    projects = db.query(models.Project).filter(
        models.Project.user_id == current_user["id"]
    ).all()
    return {"projects": [{"id": p.id, "name": p.name} for p in projects]}

@app.get("/api/projects/{project_id}", response_model=schemas.ProjectResponse)
def get_project(
    project_id: int,
    current_user: dict = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user["id"]
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"id": project.id, "name": project.name}

# Task endpoints
@app.post("/api/projects/{project_id}/tasks", response_model=schemas.TaskResponse)
def create_task(
    project_id: int,
    task: schemas.TaskCreate,
    current_user: dict = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user["id"]
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Проверить доступность ресурсов
    quantities = task.resource_quantities or {}
    for resource_id in task.resource_ids:
        resource = db.query(models.Resource).filter(
            models.Resource.id == resource_id,
            models.Resource.project_id == project_id
        ).first()
        if not resource:
            raise HTTPException(status_code=400, detail=f"Resource {resource_id} not found")
        
        quantity = quantities.get(resource_id, 1)
        
        if resource.type == 'material':
            used = db.execute(
                text("SELECT COALESCE(SUM(quantity), 0) FROM task_resource_assignment WHERE resource_id = :rid"),
                {"rid": resource_id}
            ).scalar()
            remaining = resource.availability - used
            if quantity > remaining:
                raise HTTPException(
                    status_code=400,
                    detail=f"Недостаточно ресурса '{resource.name}': доступно {remaining}, запрошено {quantity}"
                )
        else:
            if quantity > resource.availability:
                raise HTTPException(
                    status_code=400,
                    detail=f"Недостаточно ресурса '{resource.name}': доступно {resource.availability}, запрошено {quantity}"
                )
    
    db_task = models.Task(
        project_id=project_id,
        name=task.name,
        duration=task.duration,
        status="pending"
    )
    db.add(db_task)
    db.flush()
    
    # Add dependencies
    for dep_id in task.dependencies:
        dep_task = db.query(models.Task).filter(
            models.Task.id == dep_id,
            models.Task.project_id == project_id
        ).first()
        if not dep_task:
            raise HTTPException(status_code=400, detail=f"Dependency task {dep_id} not found")
        
        db_dependency = models.Dependency(
            task_id=db_task.id,
            depends_on_task_id=dep_id
        )
        db.add(db_dependency)
    
    # Add resources
    for resource_id in task.resource_ids:
        resource = db.query(models.Resource).filter(
            models.Resource.id == resource_id,
            models.Resource.project_id == project_id
        ).first()
        if not resource:
            raise HTTPException(status_code=400, detail=f"Resource {resource_id} not found")
        db_task.resources.append(resource)
    
    db.commit()
    db.refresh(db_task)
    
    # Обновить quantity
    for resource_id in task.resource_ids:
        quantity = quantities.get(resource_id, 1)
        db.execute(
            text("UPDATE task_resource_assignment SET quantity = :q WHERE task_id = :tid AND resource_id = :rid"),
            {"q": quantity, "tid": db_task.id, "rid": resource_id}
        )
    db.commit()
    
    trigger_auto_recalc(project_id, db)
    
    return {
        "id": db_task.id,
        "name": db_task.name,
        "duration": db_task.duration,
        "dependencies": task.dependencies,
        "resource_ids": task.resource_ids,
        "resource_quantities": quantities
    }

@app.get("/api/projects/{project_id}/tasks", response_model=schemas.TaskListResponse)
def list_tasks(
    project_id: int,
    current_user: dict = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user["id"]
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    tasks = db.query(models.Task).filter(models.Task.project_id == project_id).all()
    
    result = []
    for task in tasks:
        dependencies = [d.depends_on_task_id for d in task.dependencies]
        resource_ids = [r.id for r in task.resources]
        
        resource_quantities = {}
        for r in task.resources:
            qty = db.execute(
                text("SELECT quantity FROM task_resource_assignment WHERE task_id = :tid AND resource_id = :rid"),
                {"tid": task.id, "rid": r.id}
            ).scalar() or 1
            resource_quantities[r.id] = qty
        
        result.append({
            "id": task.id,
            "name": task.name,
            "duration": task.duration,
            "dependencies": dependencies,
            "resource_ids": resource_ids,
            "resource_quantities": resource_quantities
        })
    
    return {"tasks": result}

@app.put("/api/tasks/{task_id}", response_model=schemas.TaskResponse)
def update_task(
    task_id: int,
    task_update: schemas.TaskUpdate,
    current_user: dict = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(models.Task).join(models.Project).filter(
        models.Task.id == task_id,
        models.Project.user_id == current_user["id"]
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task_update.name is not None:
        task.name = task_update.name
    if task_update.duration is not None:
        task.duration = task_update.duration
    
    if task_update.dependencies is not None:
        db.query(models.Dependency).filter(models.Dependency.task_id == task_id).delete()
        for dep_id in task_update.dependencies:
            db_dependency = models.Dependency(
                task_id=task_id,
                depends_on_task_id=dep_id
            )
            db.add(db_dependency)
    
    if task_update.resource_ids is not None:
        task.resources.clear()
        db.commit()
        
        quantities = task_update.resource_quantities or {}
        for resource_id in task_update.resource_ids:
            resource = db.query(models.Resource).filter(
                models.Resource.id == resource_id,
                models.Resource.project_id == task.project_id
            ).first()
            if resource:
                task.resources.append(resource)
                db.commit()
                
                quantity = quantities.get(resource_id, 1)
                db.execute(
                    text("UPDATE task_resource_assignment SET quantity = :q WHERE task_id = :tid AND resource_id = :rid"),
                    {"q": quantity, "tid": task_id, "rid": resource_id}
                )
                db.commit()
    
    db.commit()
    db.refresh(task)
    
    trigger_auto_recalc(task.project_id, db)
    
    dependencies = [d.depends_on_task_id for d in task.dependencies]
    resource_ids = [r.id for r in task.resources]
    resource_quantities = {}
    for r in task.resources:
        qty = db.execute(
            text("SELECT quantity FROM task_resource_assignment WHERE task_id = :tid AND resource_id = :rid"),
            {"tid": task.id, "rid": r.id}
        ).scalar() or 1
        resource_quantities[r.id] = qty
    
    return {
        "id": task.id,
        "name": task.name,
        "duration": task.duration,
        "dependencies": dependencies,
        "resource_ids": resource_ids,
        "resource_quantities": resource_quantities
    }

@app.delete("/api/tasks/{task_id}")
def delete_task(
    task_id: int,
    current_user: dict = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(models.Task).join(models.Project).filter(
        models.Task.id == task_id,
        models.Project.user_id == current_user["id"]
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    project_id = task.project_id
    
    db.delete(task)
    db.commit()
    
    trigger_auto_recalc(project_id, db)
    
    return {"message": "Task deleted successfully"}


# Resource endpoints

@app.get("/api/projects/{project_id}/plan/export-json")
def export_plan_json(
    project_id: int,
    current_user: dict = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user["id"]
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    plan = db.query(models.Plan).filter(
        models.Plan.project_id == project_id
    ).order_by(models.Plan.created_at.desc()).first()
    
    if not plan or plan.status != "done" or not plan.data:
        raise HTTPException(status_code=404, detail="No completed plan found")
    
    # Получить полную информацию о задачах и ресурсах
    tasks = db.query(models.Task).filter(models.Task.project_id == project_id).all()
    resources = db.query(models.Resource).filter(models.Resource.project_id == project_id).all()
    
    task_map = {t.id: t for t in tasks}
    resource_map = {r.id: r for r in resources}
    
    export_data = {
        "project_name": project.name,
        "resources": [
            {
                "name": r.name,
                "type": r.type,
                "availability": r.availability
            }
            for r in resources
        ],
        "tasks": []
    }
    
    for t in tasks:
        task_data = {
            "name": t.name,
            "duration": t.duration,
            "dependencies": [task_map[d.depends_on_task_id].name for d in t.dependencies if d.depends_on_task_id in task_map],
            "resources": []
        }
        
        for r in t.resources:
            qty = db.execute(
                text("SELECT quantity FROM task_resource_assignment WHERE task_id = :tid AND resource_id = :rid"),
                {"tid": t.id, "rid": r.id}
            ).scalar() or 1
            task_data["resources"].append({
                "resource_name": r.name,
                "quantity": qty
            })
        
        export_data["tasks"].append(task_data)
    
    import json
    from fastapi.responses import StreamingResponse
    
    json_data = json.dumps(export_data, ensure_ascii=False, indent=2)
    
    return StreamingResponse(
        iter([json_data]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=plan_{project_id}.json"}
    )

@app.post("/api/projects/import")
def import_project(
    import_data: dict,
    current_user: dict = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    project_name = import_data.get("project_name")
    if not project_name:
        raise HTTPException(status_code=400, detail="Project name is required")
    
    # Создать проект
    db_project = models.Project(name=project_name, user_id=current_user["id"])
    db.add(db_project)
    db.flush()
    
    # Создать ресурсы
    resource_map = {}
    for idx, res in enumerate(import_data.get("resources", [])):
        res_name = res.get("name") or f"Resource {idx + 1}"
        
        db_resource = models.Resource(
            project_id=db_project.id,
            name=res_name,
            type=res.get("type", "human"),
            availability=res.get("availability", 1)
        )
        db.add(db_resource)
        db.flush()
        resource_map[res_name] = db_resource
    
    # Создать задачи
    task_map = {}
    for idx, task_data in enumerate(import_data.get("tasks", [])):
        task_name = task_data.get("name") or f"Task {task_data.get('task_id', idx + 1)}"
        duration = task_data.get("duration", 60)
        
        db_task = models.Task(
            project_id=db_project.id,
            name=task_name,
            duration=duration,
            status="pending"
        )
        db.add(db_task)
        db.flush()
        task_map[task_name] = db_task
    
    # Добавить зависимости
    for task_data in import_data.get("tasks", []):
        task_name = task_data.get("name") or f"Task {task_data.get('task_id', '')}"
        task = task_map.get(task_name)
        if not task:
            continue
        
        for dep_name in task_data.get("dependencies", []):
            dep_task = task_map.get(dep_name)
            if dep_task:
                db_dependency = models.Dependency(
                    task_id=task.id,
                    depends_on_task_id=dep_task.id
                )
                db.add(db_dependency)
    
    # Добавить ресурсы к задачам
    for task_data in import_data.get("tasks", []):
        task_name = task_data.get("name") or f"Task {task_data.get('task_id', '')}"
        task = task_map.get(task_name)
        if not task:
            continue
        
        for res_assign in task_data.get("resources", []):
            resource = resource_map.get(res_assign.get("resource_name") or res_assign.get("name"))
            if resource:
                task.resources.append(resource)
                db.flush()
                
                quantity = res_assign.get("quantity", 1)
                db.execute(
                    text("UPDATE task_resource_assignment SET quantity = :q WHERE task_id = :tid AND resource_id = :rid"),
                    {"q": quantity, "tid": task.id, "rid": resource.id}
                )
    
    db.commit()
    db.refresh(db_project)
    
    trigger_auto_recalc(db_project.id, db)
    
    return {"id": db_project.id, "name": db_project.name}

@app.post("/api/projects/{project_id}/resources", response_model=schemas.ResourceResponse)
def create_resource(
    project_id: int,
    resource: schemas.ResourceCreate,
    current_user: dict = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user["id"]
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    db_resource = models.Resource(
        project_id=project_id,
        name=resource.name,
        type=resource.type,
        availability=resource.availability
    )
    db.add(db_resource)
    db.commit()
    db.refresh(db_resource)
    
    trigger_auto_recalc(project_id, db)
    
    return {
        "id": db_resource.id,
        "name": db_resource.name,
        "type": db_resource.type,
        "availability": db_resource.availability
    }

@app.get("/api/projects/{project_id}/resources", response_model=schemas.ResourceListResponse)
def list_resources(
    project_id: int,
    current_user: dict = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user["id"]
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    resources = db.query(models.Resource).filter(
        models.Resource.project_id == project_id
    ).all()
    
    return {
        "resources": [
            {
                "id": r.id,
                "name": r.name,
                "type": r.type,
                "availability": r.availability
            }
            for r in resources
        ]
    }

@app.put("/api/resources/{resource_id}", response_model=schemas.ResourceResponse)
def update_resource(
    resource_id: int,
    resource_update: schemas.ResourceUpdate,
    current_user: dict = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    resource = db.query(models.Resource).join(models.Project).filter(
        models.Resource.id == resource_id,
        models.Project.user_id == current_user["id"]
    ).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    if resource_update.name is not None:
        resource.name = resource_update.name
    if resource_update.type is not None:
        resource.type = resource_update.type
    if resource_update.availability is not None:
        resource.availability = resource_update.availability
    
    db.commit()
    db.refresh(resource)
    
    trigger_auto_recalc(resource.project_id, db)
    
    return {
        "id": resource.id,
        "name": resource.name,
        "type": resource.type,
        "availability": resource.availability
    }

@app.delete("/api/resources/{resource_id}")
def delete_resource(
    resource_id: int,
    current_user: dict = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    resource = db.query(models.Resource).join(models.Project).filter(
        models.Resource.id == resource_id,
        models.Project.user_id == current_user["id"]
    ).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    tasks_count = db.execute(
        text("SELECT COUNT(*) FROM task_resource_assignment WHERE resource_id = :rid"),
        {"rid": resource_id}
    ).scalar()
    
    if tasks_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Невозможно удалить ресурс: он используется в {tasks_count} задачах"
        )
    
    project_id = resource.project_id
    
    db.delete(resource)
    db.commit()
    
    trigger_auto_recalc(project_id, db)
    
    return {"message": "Resource deleted successfully"}

@app.post("/api/projects/{project_id}/plan/calculate", response_model=schemas.PlanCalculateResponse)
def calculate_plan(
    project_id: int,
    current_user: dict = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user["id"]
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    db_plan = models.Plan(project_id=project_id, status="pending")
    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    
    try:
        from .tasks import calculate_plan_task
        task = calculate_plan_task.delay(db_plan.id)
        logger.info(f"Plan calculation task {task.id} started")
    except Exception as e:
        logger.warning(f"Celery not available: {e}. Running synchronously.")
        from .planner import run_planning_algorithm
        
        tasks = db.query(models.Task).filter(models.Task.project_id == project_id).all()
        resources = db.query(models.Resource).filter(models.Resource.project_id == project_id).all()
        
        tasks_data = []
        for t in tasks:
            resource_quantities = {}
            for r in t.resources:
                qty = db.execute(
                    text("SELECT quantity FROM task_resource_assignment WHERE task_id = :tid AND resource_id = :rid"),
                    {"tid": t.id, "rid": r.id}
                ).scalar() or 1
                resource_quantities[r.id] = qty
            
            tasks_data.append({
                "id": t.id,
                "name": t.name,
                "duration": t.duration,
                "resource_ids": [r.id for r in t.resources],
                "resource_quantities": resource_quantities
            })
        
        resources_data = [
            {
                "id": r.id,
                "name": r.name,
                "type": r.type,
                "availability": r.availability
            }
            for r in resources
        ]
        
        dependencies_data = []
        for task in tasks:
            for dep in task.dependencies:
                dependencies_data.append({
                    "task_id": task.id,
                    "depends_on_task_id": dep.depends_on_task_id
                })
        
        schedule = run_planning_algorithm(project_id, tasks_data, resources_data, dependencies_data)
        
        if schedule:
            db_plan.status = "done"
            db_plan.data = {"tasks": schedule}
        else:
            db_plan.status = "error"
            db_plan.data = {"error": "Невозможно построить план"}
        
        db.commit()
    
    return {"plan_id": db_plan.id, "status": db_plan.status}


@app.get("/api/projects/{project_id}/plan/latest", response_model=schemas.PlanResponse)
def get_latest_plan(
    project_id: int,
    current_user: dict = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user["id"]
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    plan = db.query(models.Plan).filter(
        models.Plan.project_id == project_id
    ).order_by(models.Plan.created_at.desc()).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="No plans found for this project")
    
    return {
        "id": plan.id,
        "status": plan.status,
        "data": plan.data,
        "created_at": plan.created_at
    }

@app.get("/api/projects/{project_id}/plan/export")
def export_plan_csv(
    project_id: int,
    current_user: dict = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user["id"]
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    plan = db.query(models.Plan).filter(
        models.Plan.project_id == project_id
    ).order_by(models.Plan.created_at.desc()).first()
    
    if not plan or plan.status != "done" or not plan.data:
        raise HTTPException(status_code=404, detail="No completed plan found")
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Task ID", "Name", "Start (min)", "End (min)", "Duration (min)"])
    
    tasks = db.query(models.Task).filter(models.Task.project_id == project_id).all()
    task_dict = {t.id: t.name for t in tasks}
    
    for t in plan.data.get("tasks", []):
        writer.writerow([
            t["task_id"],
            task_dict.get(t["task_id"], "Unknown"),
            t["start_time"],
            t["end_time"],
            t["end_time"] - t["start_time"]
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=plan_{project_id}.csv"}
    )

@app.get("/health")
def health_check():
    return {"status": "healthy"}