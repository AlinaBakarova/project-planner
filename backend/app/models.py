from sqlalchemy import Column, Integer, String, Float, ForeignKey, JSON, DateTime, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

# Association table for Task-Resource many-to-many
task_resource_association = Table(
    'task_resource_assignment',
    Base.metadata,
    Column('task_id', Integer, ForeignKey('tasks.id'), primary_key=True),
    Column('resource_id', Integer, ForeignKey('resources.id'), primary_key=True),
    Column('quantity', Integer, default=1, nullable=False)
)

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")

class Project(Base):
    __tablename__ = 'projects'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    name = Column(String, nullable=False)
    
    user = relationship("User", back_populates="projects")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    resources = relationship("Resource", back_populates="project", cascade="all, delete-orphan")
    plans = relationship("Plan", back_populates="project", cascade="all, delete-orphan")

class Task(Base):
    __tablename__ = 'tasks'
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    name = Column(String, nullable=False)
    duration = Column(Float, nullable=False)  # in hours
    status = Column(String, default='pending')
    
    project = relationship("Project", back_populates="tasks")
    resources = relationship("Resource", secondary=task_resource_association, back_populates="tasks")
    
    # Dependencies relationship
    dependencies = relationship(
        "Dependency",
        foreign_keys="Dependency.task_id",
        back_populates="task",
        cascade="all, delete-orphan"
    )
    dependents = relationship(
        "Dependency",
        foreign_keys="Dependency.depends_on_task_id",
        back_populates="depends_on",
        cascade="all, delete-orphan"
    )

class Dependency(Base):
    __tablename__ = 'dependencies'
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False)
    depends_on_task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False)
    
    task = relationship("Task", foreign_keys=[task_id], back_populates="dependencies")
    depends_on = relationship("Task", foreign_keys=[depends_on_task_id], back_populates="dependents")

class Resource(Base):
    __tablename__ = 'resources'
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    availability = Column(JSON, nullable=False)  # {"days": [1,2,3], "hours": [9,10,11]}
    
    project = relationship("Project", back_populates="resources")
    tasks = relationship("Task", secondary=task_resource_association, back_populates="resources")

class Plan(Base):
    __tablename__ = 'plans'
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    data = Column(JSON, nullable=True)
    status = Column(String, default='pending')  # pending, calculating, done, error
    created_at = Column(DateTime, default=datetime.utcnow)
    
    project = relationship("Project", back_populates="plans")
