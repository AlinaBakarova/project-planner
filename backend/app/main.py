from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import List
from datetime import datetime
import os

from . import models, schemas, auth
from .planner import run_planning_algorithm

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./project.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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

# Auth endpoints
@app.post("/api/auth/register", response_model=schemas.TokenResponse)
def register(user: schemas.UserRegister, db: Session = Depends(get_db)):
    # Check if user exists
    existing_user = db.query(models.User).filter(models.User.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Create new user
    hashed_password = auth.hash_password(user.password)
    db_user = models.User(username=user.username, password_hash=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Generate token
    token = auth.create_access_token(
        data={"sub": str(db_user.id), "username": db_user.username}
    )
    return {"token": token}

@app.post("/api/auth/login", response_model=schemas.TokenResponse)
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    # Find user
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if not db_user or not auth.verify_password(user.password, db_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # Generate token
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
    # Verify project ownership
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user["id"]
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Create task
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
        # Verify dependency exists and belongs to same project
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
    
    return {
        "id": db_task.id,
        "name": db_task.name,
        "duration": db_task.duration,
        "dependencies": task.dependencies,
        "resource_ids": task.resource_ids
    }

@app.get("/api/projects/{project_id}/tasks", response_model=schemas.TaskListResponse)
def list_tasks(
    project_id: int,
    current_user: dict = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    # Verify project ownership
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user["id"]
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    tasks = db.query(models.Task).filter(models.Task.project_id == project_id).all()
    
    result = []
    for task in tasks:
        # Get dependencies
        dependencies = [d.depends_on_task_id for d in task.dependencies]
        # Get resources
        resource_ids = [r.id for r in task.resources]
        
        result.append({
            "id": task.id,
            "name": task.name,
            "duration": task.duration,
            "dependencies": dependencies,
            "resource_ids": resource_ids
        })
    
    return {"tasks": result}

@app.put("/api/tasks/{task_id}", response_model=schemas.TaskResponse)
def update_task(
    task_id: int,
    task_update: schemas.TaskUpdate,
    current_user: dict = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    # Get task with project ownership check
    task = db.query(models.Task).join(models.Project).filter(
        models.Task.id == task_id,
        models.Project.user_id == current_user["id"]
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update basic fields
    if task_update.name is not None:
        task.name = task_update.name
    if task_update.duration is not None:
        task.duration = task_update.duration
    
    # Update dependencies
    if task_update.dependencies is not None:
        # Remove old dependencies
        db.query(models.Dependency).filter(models.Dependency.task_id == task_id).delete()
        
        # Add new dependencies
        for dep_id in task_update.dependencies:
            dep_task = db.query(models.Task).filter(
                models.Task.id == dep_id,
                models.Task.project_id == task.project_id
            ).first()
            if not dep_task:
                raise HTTPException(status_code=400, detail=f"Dependency task {dep_id} not found")
            
            db_dependency = models.Dependency(
                task_id=task_id,
                depends_on_task_id=dep_id
            )
            db.add(db_dependency)
    
    # Update resources
    if task_update.resource_ids is not None:
        task.resources.clear()
        for resource_id in task_update.resource_ids:
            resource = db.query(models.Resource).filter(
                models.Resource.id == resource_id,
                models.Resource.project_id == task.project_id
            ).first()
            if not resource:
                raise HTTPException(status_code=400, detail=f"Resource {resource_id} not found")
            task.resources.append(resource)
    
    db.commit()
    db.refresh(task)
    
    # Get updated dependencies and resources
    dependencies = [d.depends_on_task_id for d in task.dependencies]
    resource_ids = [r.id for r in task.resources]
    
    return {
        "id": task.id,
        "name": task.name,
        "duration": task.duration,
        "dependencies": dependencies,
        "resource_ids": resource_ids
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
    
    db.delete(task)
    db.commit()
    return {"message": "Task deleted successfully"}

# Resource endpoints
@app.post("/api/projects/{project_id}/resources", response_model=schemas.ResourceResponse)
def create_resource(
    project_id: int,
    resource: schemas.ResourceCreate,
    current_user: dict = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    # Verify project ownership
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
    # Verify project ownership
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
    
    db.delete(resource)
    db.commit()
    return {"message": "Resource deleted successfully"}

# Plan endpoints
@app.post("/api/projects/{project_id}/plan/calculate", response_model=schemas.PlanCalculateResponse)
def calculate_plan(
    project_id: int,
    current_user: dict = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    # Verify project ownership
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user["id"]
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Create plan record
    db_plan = models.Plan(project_id=project_id, status="pending")
    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    
    # Here you would trigger Celery task
    # For now, we'll run it synchronously (in production, use Celery)
    try:
        # Update status to calculating
        db_plan.status = "calculating"
        db.commit()
        
        # Get all tasks with dependencies and resources
        tasks = db.query(models.Task).filter(models.Task.project_id == project_id).all()
        resources = db.query(models.Resource).filter(models.Resource.project_id == project_id).all()
        
        # Prepare data for algorithm
        tasks_data = [
            {
                "id": t.id,
                "name": t.name,
                "duration": t.duration,
                "resource_ids": [r.id for r in t.resources]
            }
            for t in tasks
        ]
        
        resources_data = [
            {
                "id": r.id,
                "name": r.name,
                "type": r.type,
                "availability": r.availability
            }
            for r in resources
        ]
        
        dependencies_data = {}
        for task in tasks:
            dependencies_data[task.id] = [d.depends_on_task_id for d in task.dependencies]
        
        # Run planning algorithm
        schedule = run_planning_algorithm(project_id, tasks_data, resources_data, dependencies_data)
        
        if schedule:
            db_plan.status = "done"
            db_plan.data = schedule
        else:
            db_plan.status = "error"
            db_plan.data = {"error": "Невозможно построить план"}
        
        db.commit()
        
    except Exception as e:
        db_plan.status = "error"
        db_plan.data = {"error": str(e)}
        db.commit()
    
    return {"plan_id": db_plan.id, "status": db_plan.status}

@app.get("/api/projects/{project_id}/plan/latest", response_model=schemas.PlanResponse)
def get_latest_plan(
    project_id: int,
    current_user: dict = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    # Verify project ownership
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user["id"]
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get latest plan
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

# Health check
@app.get("/health")
def health_check():
    return {"status": "healthy"}
