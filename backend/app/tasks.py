from .celery_app import celery_app
from .planner import run_planning_algorithm
from . import models
from .database import SessionLocal
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="calculate_plan_task")
def calculate_plan_task(self, plan_id: int):
    """
    Celery task for asynchronous plan calculation.
    """
    logger.info(f"Plan calculation started for plan {plan_id}")
    
    db = SessionLocal()
    try:
        plan = db.query(models.Plan).filter(models.Plan.id == plan_id).first()
        if not plan:
            logger.error(f"Plan {plan_id} not found")
            return {"status": "error", "message": "Plan not found"}
        
        plan.status = "calculating"
        db.commit()
        logger.info(f"Plan {plan_id} status updated to calculating")
        
        project_id = plan.project_id
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
        
        logger.info(f"Running planning algorithm for plan {plan_id}")
        schedule = run_planning_algorithm(project_id, tasks_data, resources_data, dependencies_data)
        
        if schedule:
            plan.status = "done"
            plan.data = {"tasks": schedule}
            logger.info(f"Plan {plan_id} completed successfully")
        else:
            plan.status = "error"
            plan.data = {"error": "Невозможно построить план"}
            logger.warning(f"Plan {plan_id} failed: unable to build schedule")
        
        db.commit()
        
        return {"plan_id": plan_id, "status": plan.status}
        
    except Exception as e:
        logger.error(f"Error calculating plan {plan_id}: {str(e)}")
        try:
            plan = db.query(models.Plan).filter(models.Plan.id == plan_id).first()
            if plan:
                plan.status = "error"
                plan.data = {"error": str(e)}
                db.commit()
        except:
            pass
        return {"plan_id": plan_id, "status": "error", "message": str(e)}
    finally:
        db.close()