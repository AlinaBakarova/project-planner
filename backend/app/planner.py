import sys
import os
from pathlib import Path

# Add algorithm directory to path
ALGORITHM_PATH = Path(__file__).parent.parent.parent / "algorithm"
sys.path.append(str(ALGORITHM_PATH))

from .scheduler import calculate_schedule

def run_planning_algorithm(project_id: int, tasks: list, resources: list, dependencies: dict):
    """
    Wrapper function to run the planning algorithm
    """
    return calculate_schedule(tasks, resources, dependencies)
