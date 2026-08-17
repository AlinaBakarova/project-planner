from .celery_app import celery_app
from .planner import run_planning_algorithm
from . import models
from .database import SessionLocal
import logging

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="calculate_plan_task")
def calculate_plan_task(self, plan_id: int):
    """
    Celery task for asynchronous plan calculation.
    
    Args:
        plan_id: ID of the Plan record to process
    """
    logger.info(f"Plan calculation started for plan {plan_id}")
    
    db = SessionLocal()
    try:
        # Get plan from database
        plan = db.query(models.Plan).filter(models.Plan.id == plan_id).first()
        if not plan:
            logger.error(f"Plan {plan_id} not found")
            return {"status": "error", "message": "Plan not found"}
        
        # Update status to "calculating"
        plan.status = "calculating"
        db.commit()
        logger.info(f"Plan {plan_id} status updated to calculating")
        
        # Get project tasks and resources
        project_id = plan.project_id
        tasks = db.query(models.Task).filter(
            models.Task.project_id == project_id
        ).all()
        resources = db.query(models.Resource).filter(
            models.Resource.project_id == project_id
        ).all()
        
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
        
        dependencies_data = []
        for task in tasks:
            for dep in task.dependencies:
                dependencies_data.append({
                    "task_id": task.id,
                    "depends_on_task_id": dep.depends_on_task_id
                })


        
        # Run planning algorithm
        logger.info(f"Running planning algorithm for plan {plan_id}")
        schedule = run_planning_algorithm(
            project_id,
            tasks_data, 
            resources_data, 
            dependencies_data
        )
        
        # Update plan with result
        if schedule:
            plan.status = "done"
            plan.data = {"tasks": schedule}
            logger.info(f"Plan {plan_id} completed successfully")
        else:
            plan.status = "error"
            plan.data = {"error": "Невозможно построить план"}
            logger.warning(f"Plan {plan_id} failed: unable to build schedule")
        
        db.commit()
        
        return {
            "plan_id": plan_id,
            "status": plan.status
        }
        
    except Exception as e:
        logger.error(f"Error calculating plan {plan_id}: {str(e)}")
        
        # Update plan status to error
        try:
            plan = db.query(models.Plan).filter(models.Plan.id == plan_id).first()
            if plan:
                plan.status = "error"
                plan.data = {"error": str(e)}
                db.commit()
        except:
            pass
        
        return {
            "plan_id": plan_id,
            "status": "error",
            "message": str(e)
        }
        
    finally:
        db.close()
