# algorithm/scheduler.py

from typing import List, Dict, Optional, Set, Tuple
from collections import defaultdict
import heapq


def calculate_schedule(
    tasks: List[Dict],
    dependencies: List[Dict],
    resources: List[Dict]
) -> Optional[List[Dict]]:
    """
    Строит допустимое расписание с учетом зависимостей и ограничений на ресурсы.
    
    Args:
        tasks: список задач [{id, duration, resource_ids}]
        dependencies: список зависимостей [{task_id, depends_on_task_id}]
        resources: список ресурсов [{id, type, availability}]
    
    Returns:
        Список [{task_id, start_time, end_time}] или None, если план невозможен
    """
    
    # Создаем словари для быстрого доступа
    task_dict = {task['id']: task for task in tasks}
    resource_dict = {res['id']: res for res in resources}
    
    # Проверка на корректность входных данных
    for task in tasks:
        if task['duration'] < 0:
            return None
        for resource_id in task.get('resource_ids', []):
            if resource_id not in resource_dict:
                return None
    
    for dep in dependencies:
        if dep['task_id'] not in task_dict or dep['depends_on_task_id'] not in task_dict:
            return None
    
    # Проверка на циклические зависимости
    if _has_cycle(tasks, dependencies):
        return None
    
    # Строим граф зависимостей
    depends_on = defaultdict(set)  # task_id -> set of task_ids it depends on
    dependents = defaultdict(set)  # task_id -> set of task_ids that depend on it
    
    for dep in dependencies:
        depends_on[dep['task_id']].add(dep['depends_on_task_id'])
        dependents[dep['depends_on_task_id']].add(dep['task_id'])
    
    # Инициализация счетчиков зависимостей
    remaining_deps = {task['id']: len(depends_on[task['id']]) for task in tasks}
    
    # Множество готовых к выполнению задач
    ready_tasks = set()
    for task_id in remaining_deps:
        if remaining_deps[task_id] == 0:
            ready_tasks.add(task_id)
    
    # Словарь для отслеживания занятости ресурсов
    # resource_id -> список (end_time, task_id) для активных задач
    resource_usage = defaultdict(list)
    
    # Словарь для хранения расписания
    schedule = {task['id']: None for task in tasks}
    
    # Текущее время
    current_time = 0
    
    # Множество завершенных задач
    completed_tasks = set()
    
    # Множество задач, ожидающих назначения
    waiting_tasks = set()
    
    # Основной цикл симуляции
    while len(completed_tasks) < len(tasks):
        # Находим все задачи, которые завершились к текущему времени
        newly_completed = set()
        
        for task_id, task_schedule in schedule.items():
            if task_schedule is not None and task_schedule['end_time'] <= current_time and task_id not in completed_tasks:
                newly_completed.add(task_id)
        
        # Обрабатываем завершенные задачи
        for task_id in newly_completed:
            completed_tasks.add(task_id)
            waiting_tasks.discard(task_id)
            
            # Освобождаем ресурсы
            task = task_dict[task_id]
            for resource_id in task.get('resource_ids', []):
                resource_usage[resource_id] = [
                    (end_time, tid) for end_time, tid in resource_usage[resource_id] 
                    if tid != task_id
                ]
            
            # Добавляем новые готовые задачи
            for dependent_task_id in dependents[task_id]:
                remaining_deps[dependent_task_id] -= 1
                if remaining_deps[dependent_task_id] == 0:
                    ready_tasks.add(dependent_task_id)
        
        # Переносим готовые задачи в ожидающие
        waiting_tasks.update(ready_tasks)
        ready_tasks.clear()
        
        if not waiting_tasks:
            # Если нет ожидающих задач, но есть незавершенные
            if len(completed_tasks) < len(tasks):
                # Находим время следующего завершения задачи
                next_completion_time = float('inf')
                for task_id, task_schedule in schedule.items():
                    if task_schedule is not None and task_id not in completed_tasks:
                        next_completion_time = min(next_completion_time, task_schedule['end_time'])
                
                if next_completion_time == float('inf'):
                    return None  # Deadlock
                
                current_time = next_completion_time
            continue
        
        # Пытаемся назначить ожидающие задачи
        assigned_tasks = set()
        
        # Сортируем задачи по приоритету (по длительности - сначала короткие)
        sorted_waiting = sorted(waiting_tasks, key=lambda tid: task_dict[tid]['duration'])
        
        for task_id in sorted_waiting:
            task = task_dict[task_id]
            resource_ids = task.get('resource_ids', [])
            
            # Проверяем доступность ресурсов
            can_assign = True
            for resource_id in resource_ids:
                resource = resource_dict[resource_id]
                available = resource['availability']
                used = len(resource_usage[resource_id])
                
                if used >= available:
                    can_assign = False
                    break
            
            if can_assign:
                # Назначаем задачу
                start_time = current_time
                end_time = current_time + task['duration']
                
                schedule[task_id] = {
                    'task_id': task_id,
                    'start_time': start_time,
                    'end_time': end_time
                }
                
                # Занимаем ресурсы
                for resource_id in resource_ids:
                    resource_usage[resource_id].append((end_time, task_id))
                
                assigned_tasks.add(task_id)
        
        # Удаляем назначенные задачи из ожидающих
        waiting_tasks -= assigned_tasks
        
        # Определяем следующее событие
        next_event_time = float('inf')
        
        # Время завершения активных задач
        for task_id, task_schedule in schedule.items():
            if task_schedule is not None and task_id not in completed_tasks:
                next_event_time = min(next_event_time, task_schedule['end_time'])
        
        if waiting_tasks and next_event_time == float('inf'):
            return None  # Deadlock - есть задачи, но нет активных
        
        if waiting_tasks:
            # Есть нераспределенные задачи - ждем освобождения ресурсов
            current_time = next_event_time
        else:
            # Все задачи распределены - переходим к следующему завершению
            if next_event_time != float('inf'):
                current_time = next_event_time
    
    # Формируем результат
    result = []
    for task_id in sorted(schedule.keys()):
        result.append(schedule[task_id])
    
    return result


def _has_cycle(tasks: List[Dict], dependencies: List[Dict]) -> bool:
    """
    Проверяет наличие циклов в графе зависимостей.
    """
    # Строим граф
    graph = defaultdict(set)
    for dep in dependencies:
        graph[dep['depends_on_task_id']].add(dep['task_id'])
    
    # DFS для поиска циклов
    WHITE, GRAY, BLACK = 0, 1, 2
    colors = {task['id']: WHITE for task in tasks}
    
    def dfs(node):
        if colors[node] == GRAY:
            return True  # Найден цикл
        if colors[node] == BLACK:
            return False
        
        colors[node] = GRAY
        for neighbor in graph[node]:
            if dfs(neighbor):
                return True
        
        colors[node] = BLACK
        return False
    
    for task_id in colors:
        if colors[task_id] == WHITE:
            if dfs(task_id):
                return True
    
    return False
