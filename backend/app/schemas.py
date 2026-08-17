from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

# Auth schemas
class UserRegister(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    token: str

# Project schemas
class ProjectCreate(BaseModel):
    name: str

class ProjectResponse(BaseModel):
    id: int
    name: str

class ProjectListResponse(BaseModel):
    projects: List[ProjectResponse]

# Task schemas
class TaskCreate(BaseModel):
    name: str
    duration: float
    dependencies: List[int] = []
    resource_ids: List[int] = []

class TaskUpdate(BaseModel):
    name: Optional[str] = None
    duration: Optional[float] = None
    dependencies: Optional[List[int]] = None
    resource_ids: Optional[List[int]] = None

class TaskResponse(BaseModel):
    id: int
    name: str
    duration: float
    dependencies: List[int] = []
    resource_ids: List[int] = []

class TaskListResponse(BaseModel):
    tasks: List[TaskResponse]

# Resource schemas
class ResourceCreate(BaseModel):
    name: str
    type: str
    availability: int

class ResourceUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    availability: Optional[int] = None

class ResourceResponse(BaseModel):
    id: int
    name: str
    type: str
    availability: int

class ResourceListResponse(BaseModel):
    resources: List[ResourceResponse]

# Plan schemas
class PlanCalculateResponse(BaseModel):
    plan_id: int
    status: str

class PlanResponse(BaseModel):
    id: int
    status: str
    data: Optional[Any] = None
    created_at: datetime
